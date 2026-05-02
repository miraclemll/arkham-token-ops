#!/usr/bin/env python3
"""CLI entrypoint for the token-control-monitor skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.arkham_client import (  # noqa: E402
    ArkhamClient,
    ArkhamError,
    normalize_address_intelligence,
    normalize_holders,
    normalize_token_info,
    parse_transfer,
)
from lib.monitor_runtime import (  # noqa: E402
    install_monitor,
    monitor_logs,
    monitor_status,
    resolve_env,
    run_monitor,
    sanitize_monitor_name,
    stop_monitor,
    uninstall_monitor,
)


def print_json(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def build_client() -> ArkhamClient:
    env = resolve_env(Path.cwd())
    api_key = env.get("ARKHAM_API_KEY", "")
    return ArkhamClient(api_key=api_key)


def handle_token_report(args):
    client = build_client()
    token_info = normalize_token_info(client.get_token_info(args.chain, args.token_address))
    holders = normalize_holders(
        client.get_token_holders(args.chain, args.token_address, args.holders_limit),
        args.chain,
        args.holders_limit,
    )
    transfers = [
        parse_transfer(transfer)
        for transfer in client.get_recent_transfers(
            chain=args.chain,
            token_address=args.token_address,
            limit=args.transfers_limit,
        ).get("transfers", [])
    ]
    print_json(
        {
            "command": "token-report",
            "token": token_info,
            "holders": holders,
            "recent_transfers": transfers,
        }
    )


def handle_address_report(args):
    client = build_client()
    intelligence = normalize_address_intelligence(client.get_address_intelligence(args.address))
    transfers = [
        parse_transfer(transfer)
        for transfer in client.get_address_transfers(
            chain=args.chain,
            address=args.address,
            limit=args.transfers_limit,
        ).get("transfers", [])
    ]
    print_json(
        {
            "command": "address-report",
            "requested_chain": args.chain,
            "address": args.address,
            "intelligence": intelligence,
            "recent_transfers": transfers,
        }
    )


def handle_recent_transfers(args):
    client = build_client()
    transfers = [
        parse_transfer(transfer)
        for transfer in client.get_recent_transfers(
            chain=args.chain,
            token_address=args.token_address,
            time_last=args.time_last,
            usd_gte=args.usd_gte,
            limit=args.limit,
        ).get("transfers", [])
    ]
    print_json(
        {
            "command": "recent-transfers",
            "chain": args.chain,
            "token_address": args.token_address,
            "time_last": args.time_last,
            "usd_gte": args.usd_gte,
            "transfers": transfers,
        }
    )


def handle_resolve_token(args):
    client = build_client()
    print_json(
        {
            "command": "resolve-token",
            "query": args.query,
            **client.resolve_token(args.query),
        }
    )


def handle_monitor_install(args):
    client = build_client()
    token = normalize_token_info(client.get_token_info(args.chain, args.token_address))
    env = resolve_env(Path.cwd())
    payload = install_monitor(
        name=args.name,
        config={
            "chain": args.chain,
            "token_address": args.token_address,
            "threshold_usd": args.threshold_usd,
            "interval_sec": args.interval_sec,
            "time_last": "24h",
            "fetch_limit": 50,
            "token_name": token["name"],
            "token_symbol": token["symbol"],
            "token_pricing_id": token["pricing_id"],
        },
        env=env,
        script_path=Path(__file__).resolve(),
    )
    print_json(payload)


def handle_monitor_status(args):
    print_json(monitor_status(args.name))


def handle_monitor_logs(args):
    print_json(monitor_logs(args.name))


def handle_monitor_stop(args):
    print_json(stop_monitor(args.name))


def handle_monitor_uninstall(args):
    print_json(uninstall_monitor(args.name))


def handle_monitor_run(args):
    run_monitor(args.name)


def build_parser():
    parser = argparse.ArgumentParser(description="Token Control Monitor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_report = subparsers.add_parser("token-report", help="Analyze a token by chain and contract address.")
    token_report.add_argument("--chain", required=True)
    token_report.add_argument("--token-address", required=True)
    token_report.add_argument("--holders-limit", type=int, default=20)
    token_report.add_argument("--transfers-limit", type=int, default=20)
    token_report.set_defaults(func=handle_token_report)

    address_report = subparsers.add_parser("address-report", help="Analyze an address on a given chain.")
    address_report.add_argument("--chain", required=True)
    address_report.add_argument("--address", required=True)
    address_report.add_argument("--transfers-limit", type=int, default=20)
    address_report.set_defaults(func=handle_address_report)

    recent = subparsers.add_parser("recent-transfers", help="Inspect recent transfers for a token.")
    recent.add_argument("--chain", required=True)
    recent.add_argument("--token-address", required=True)
    recent.add_argument("--time-last", default="24h")
    recent.add_argument("--usd-gte", type=float)
    recent.add_argument("--limit", type=int, default=20)
    recent.set_defaults(func=handle_recent_transfers)

    resolve = subparsers.add_parser("resolve-token", help="Resolve a token symbol or query using Arkham search.")
    resolve.add_argument("--query", required=True)
    resolve.set_defaults(func=handle_resolve_token)

    monitor = subparsers.add_parser("monitor", help="Manage launchd-backed token monitors.")
    monitor_sub = monitor.add_subparsers(dest="monitor_command", required=True)

    monitor_install = monitor_sub.add_parser("install", help="Install and start a monitor.")
    monitor_install.add_argument("--name", required=True)
    monitor_install.add_argument("--chain", required=True)
    monitor_install.add_argument("--token-address", required=True)
    monitor_install.add_argument("--threshold-usd", required=True, type=float)
    monitor_install.add_argument("--interval-sec", required=True, type=int)
    monitor_install.set_defaults(func=handle_monitor_install)

    monitor_status_parser = monitor_sub.add_parser("status", help="Show monitor status.")
    monitor_status_parser.add_argument("--name", required=True)
    monitor_status_parser.set_defaults(func=handle_monitor_status)

    monitor_logs_parser = monitor_sub.add_parser("logs", help="Show recent monitor logs.")
    monitor_logs_parser.add_argument("--name", required=True)
    monitor_logs_parser.set_defaults(func=handle_monitor_logs)

    monitor_stop_parser = monitor_sub.add_parser("stop", help="Stop a monitor without deleting it.")
    monitor_stop_parser.add_argument("--name", required=True)
    monitor_stop_parser.set_defaults(func=handle_monitor_stop)

    monitor_uninstall_parser = monitor_sub.add_parser("uninstall", help="Stop and delete a monitor.")
    monitor_uninstall_parser.add_argument("--name", required=True)
    monitor_uninstall_parser.set_defaults(func=handle_monitor_uninstall)

    monitor_run = subparsers.add_parser("monitor-run", help=argparse.SUPPRESS)
    monitor_run.add_argument("--name", required=True)
    monitor_run.set_defaults(func=handle_monitor_run)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "name", None):
        args.name = sanitize_monitor_name(args.name)

    try:
        args.func(args)
    except (ArkhamError, RuntimeError, ValueError) as exc:
        print_json({"status": "error", "error": str(exc)})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
