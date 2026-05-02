#!/usr/bin/env python3
"""Config, launchd, and monitor runtime helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

from .arkham_client import ArkhamClient, ArkhamError, parse_transfer
from .telegram import send_message, transfer_alert_message


APP_NAME = "token-control-monitor"
TRACKED_TX_CACHE_SIZE = 1000


def app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def support_env_path() -> Path:
    return app_support_dir() / ".env"


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def logs_dir() -> Path:
    return Path.home() / "Library" / "Logs" / APP_NAME


def sanitize_monitor_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name.strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        raise RuntimeError("Monitor name must contain letters, digits, dot, underscore, or hyphen.")
    return cleaned


def monitor_dir(name: str) -> Path:
    return app_support_dir() / "monitors" / sanitize_monitor_name(name)


def monitor_paths(name: str) -> Dict[str, Path]:
    safe_name = sanitize_monitor_name(name)
    base_dir = monitor_dir(safe_name)
    label = f"com.codex.token-control-monitor.{safe_name}"
    return {
        "label": Path(label),
        "dir": base_dir,
        "config": base_dir / "config.json",
        "state": base_dir / "state.json",
        "plist": launch_agents_dir() / f"{label}.plist",
        "stdout_log": logs_dir() / f"{safe_name}.log",
        "stderr_log": logs_dir() / f"{safe_name}.err.log",
    }


def parse_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def resolve_env(cwd: Path | None = None) -> Dict[str, str]:
    cwd = cwd or Path.cwd()
    resolved: Dict[str, str] = {}
    resolved.update(parse_dotenv(support_env_path()))
    resolved.update(parse_dotenv(cwd / ".env"))
    resolved.update({key: value for key, value in os.environ.items() if value})
    return resolved


def ensure_env(env: Dict[str, str], keys: List[str]) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")


def write_support_env(env: Dict[str, str]) -> Path:
    app_support_dir().mkdir(parents=True, exist_ok=True)
    path = support_env_path()
    keys = ["ARKHAM_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    lines = [f"{key}={env[key]}" for key in keys if env.get(key)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return path


def _run_launchctl(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def _launch_target() -> str:
    return f"gui/{os.getuid()}"


def plist_text(label: str, python_exec: str, script_path: str, name: str, working_directory: str, stdout_log: str, stderr_log: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_exec}</string>
    <string>{script_path}</string>
    <string>monitor-run</string>
    <string>--name</string>
    <string>{name}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>{working_directory}</string>
  <key>StandardOutPath</key>
  <string>{stdout_log}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_log}</string>
</dict>
</plist>
"""


def install_monitor(name: str, config: Dict[str, object], env: Dict[str, str], script_path: Path) -> Dict[str, object]:
    ensure_env(env, ["ARKHAM_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    paths = monitor_paths(name)
    app_support_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    paths["dir"].mkdir(parents=True, exist_ok=True)

    write_support_env(env)

    config_payload = dict(config)
    config_payload["name"] = sanitize_monitor_name(name)
    config_payload["support_env"] = str(support_env_path())
    config_payload["installed_at"] = int(time.time())
    paths["config"].write_text(json.dumps(config_payload, indent=2, sort_keys=True) + "\n")
    if not paths["state"].exists():
        paths["state"].write_text(json.dumps({"initialized": False, "seen_tx_hashes": []}, indent=2) + "\n")

    label = str(paths["label"])
    plist_contents = plist_text(
        label=label,
        python_exec=sys.executable,
        script_path=str(script_path),
        name=sanitize_monitor_name(name),
        working_directory=str(app_support_dir()),
        stdout_log=str(paths["stdout_log"]),
        stderr_log=str(paths["stderr_log"]),
    )
    paths["plist"].write_text(plist_contents)

    target = _launch_target()
    _run_launchctl(["launchctl", "bootout", target, str(paths["plist"])])
    bootstrap = _run_launchctl(["launchctl", "bootstrap", target, str(paths["plist"])])
    if bootstrap.returncode != 0:
        raise RuntimeError(bootstrap.stderr.strip() or bootstrap.stdout.strip() or "launchctl bootstrap failed")

    kickstart = _run_launchctl(["launchctl", "kickstart", "-k", f"{target}/{label}"])
    if kickstart.returncode != 0:
        raise RuntimeError(kickstart.stderr.strip() or kickstart.stdout.strip() or "launchctl kickstart failed")

    return {
        "status": "installed",
        "name": sanitize_monitor_name(name),
        "label": label,
        "paths": {key: str(value) for key, value in paths.items() if isinstance(value, Path)},
    }


def monitor_status(name: str) -> Dict[str, object]:
    paths = monitor_paths(name)
    label = str(paths["label"])
    target = _launch_target()
    proc = _run_launchctl(["launchctl", "print", f"{target}/{label}"])
    loaded = proc.returncode == 0
    config = json.loads(paths["config"].read_text()) if paths["config"].exists() else None
    state = json.loads(paths["state"].read_text()) if paths["state"].exists() else None
    return {
        "name": sanitize_monitor_name(name),
        "loaded": loaded,
        "label": label,
        "paths": {key: str(value) for key, value in paths.items() if isinstance(value, Path)},
        "config": config,
        "state": state,
        "launchctl_output": proc.stdout.strip() if loaded else proc.stderr.strip() or proc.stdout.strip(),
    }


def tail_file(path: Path, lines: int = 50) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(errors="replace").splitlines()[-lines:]


def monitor_logs(name: str) -> Dict[str, object]:
    paths = monitor_paths(name)
    return {
        "name": sanitize_monitor_name(name),
        "stdout_log": str(paths["stdout_log"]),
        "stderr_log": str(paths["stderr_log"]),
        "stdout_tail": tail_file(paths["stdout_log"]),
        "stderr_tail": tail_file(paths["stderr_log"]),
    }


def stop_monitor(name: str) -> Dict[str, object]:
    paths = monitor_paths(name)
    label = str(paths["label"])
    result = _run_launchctl(["launchctl", "bootout", _launch_target(), str(paths["plist"])])
    return {
        "status": "stopped" if result.returncode == 0 else "not_loaded",
        "name": sanitize_monitor_name(name),
        "label": label,
        "detail": result.stderr.strip() or result.stdout.strip(),
    }


def uninstall_monitor(name: str) -> Dict[str, object]:
    stop_result = stop_monitor(name)
    paths = monitor_paths(name)
    if paths["plist"].exists():
        paths["plist"].unlink()
    if paths["dir"].exists():
        shutil.rmtree(paths["dir"])
    return {
        "status": "uninstalled",
        "name": sanitize_monitor_name(name),
        "stop_result": stop_result,
    }


def _load_monitor_config(name: str) -> Tuple[Dict[str, object], Dict[str, object], Dict[str, str], Dict[str, Path]]:
    paths = monitor_paths(name)
    if not paths["config"].exists():
        raise RuntimeError(f"Monitor config not found for '{name}'.")
    config = json.loads(paths["config"].read_text())
    state = json.loads(paths["state"].read_text()) if paths["state"].exists() else {"initialized": False, "seen_tx_hashes": []}
    env = resolve_env(app_support_dir())
    ensure_env(env, ["ARKHAM_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    return config, state, env, paths


def _save_state(paths: Dict[str, Path], state: Dict[str, object]) -> None:
    paths["state"].write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def run_monitor(name: str) -> None:
    config, state, env, paths = _load_monitor_config(name)
    client = ArkhamClient(env["ARKHAM_API_KEY"])
    seen = deque(state.get("seen_tx_hashes", []), maxlen=TRACKED_TX_CACHE_SIZE)
    running = True

    def stop_signal(signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)

    chain = str(config["chain"])
    token_address = str(config["token_address"])
    time_last = str(config.get("time_last", "24h"))
    fetch_limit = int(config.get("fetch_limit", 50))
    threshold = float(config["threshold_usd"])
    interval = int(config["interval_sec"])
    token_name = str(config.get("token_name", "Token"))
    token_symbol = str(config.get("token_symbol", ""))

    if not state.get("initialized"):
        seed = client.get_recent_transfers(chain=chain, token_address=token_address, time_last=time_last, limit=fetch_limit)
        for transfer in seed.get("transfers", []):
            parsed = parse_transfer(transfer)
            if parsed["tx_hash"] and parsed["tx_hash"] not in seen:
                seen.append(parsed["tx_hash"])
        state["initialized"] = True
        state["seen_tx_hashes"] = list(seen)
        state["last_seeded_at"] = int(time.time())
        _save_state(paths, state)

    while running:
        try:
            payload = client.get_recent_transfers(chain=chain, token_address=token_address, time_last=time_last, limit=fetch_limit)
            known = set(seen)
            new_transfers = []
            for transfer in payload.get("transfers", []):
                parsed = parse_transfer(transfer)
                if parsed["tx_hash"] and parsed["tx_hash"] not in known:
                    new_transfers.append(parsed)

            for transfer in reversed(new_transfers):
                if transfer["amount_usd"] >= threshold:
                    message = transfer_alert_message(transfer, token_name=token_name, token_symbol=token_symbol)
                    send_message(env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"], message)

            for transfer in new_transfers:
                if transfer["tx_hash"] and transfer["tx_hash"] not in seen:
                    seen.append(transfer["tx_hash"])

            state["seen_tx_hashes"] = list(seen)
            state["last_checked_at"] = int(time.time())
            _save_state(paths, state)
        except (ArkhamError, RuntimeError) as exc:
            state["last_error"] = str(exc)
            state["last_error_at"] = int(time.time())
            _save_state(paths, state)

        time.sleep(interval)
