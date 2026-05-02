---
name: token-control-monitor
description: Analyze project-controlled token supply, known address groups, holder concentration, and transfer flows. Use this skill when a user wants token control analysis, project treasury monitoring, address intelligence, whale-transfer monitoring, or a reusable macOS monitoring setup for any token.
---

# Token Control Monitor

## Overview

Use this skill for token control operations: project treasury and holder analysis, address intelligence, recent or large transfer inspection, and long-running token monitoring with Telegram alerts on macOS. Arkham is currently one supported intelligence provider, not the skill's identity.

The skill is built around one deterministic CLI entrypoint:

```bash
python3 scripts/token_control_monitor.py ...
```

Prefer this script over ad hoc API calls so outputs stay stable and launchd deployments remain manageable.

## Core Capabilities

### 1. Analyze a token

Use `token-report` when the user wants token-level context such as:

- top holders
- recent transfers
- basic token identity

If the user provides `chain + token address`, run the report directly:

```bash
python3 scripts/token_control_monitor.py token-report --chain ethereum --token-address 0xYOUR_TOKEN_ADDRESS
```

If the user only provides a symbol or fuzzy query, resolve it first:

```bash
python3 scripts/token_control_monitor.py resolve-token --query TOKEN_SYMBOL
```

Resolution rules:

- If exactly one strong match is returned, proceed and explicitly mention which token was selected.
- If multiple candidates remain, stop and ask the user which one they want.
- For deployment, do not proceed from symbol-only input when ambiguity remains.

### 2. Analyze an address

Use `address-report` when the user wants to inspect a wallet or contract:

```bash
python3 scripts/token_control_monitor.py address-report --chain ethereum --address 0x...
```

Return:

- Provider address intelligence
- recent transfers on the requested chain

If the user does not provide a chain and the context does not make it obvious, ask for the chain before acting.

### 3. Inspect recent or large transfers

Use `recent-transfers` when the user asks for recent token flows, whale activity, or large transfers:

```bash
python3 scripts/token_control_monitor.py recent-transfers --chain ethereum --token-address 0xYOUR_TOKEN_ADDRESS --usd-gte 10000 --limit 20
```

Use this for one-off inspection. For continuous monitoring, use monitor install instead.

### 4. Deploy a macOS monitor

Use `monitor install` when the user wants persistent monitoring on a Mac:

```bash
python3 scripts/token_control_monitor.py monitor install --name token-main --chain ethereum --token-address 0xYOUR_TOKEN_ADDRESS --threshold-usd 5000 --interval-sec 60
```

Behavior:

- Requires explicit `chain + token address`
- Uses REST polling by default
- Sends Telegram alerts only; Telegram is not used as a chat-command interface
- Installs a per-user LaunchAgent under `~/Library/LaunchAgents/`
- Stores monitor config and dedupe state under `~/Library/Application Support/token-control-monitor/monitors/<name>/`

Management commands:

```bash
python3 scripts/token_control_monitor.py monitor status --name token-main
python3 scripts/token_control_monitor.py monitor logs --name token-main
python3 scripts/token_control_monitor.py monitor stop --name token-main
python3 scripts/token_control_monitor.py monitor uninstall --name token-main
```

## Config Rules

Secrets never live inside the skill directory itself.

Config resolution order:

1. Process environment variables
2. `.env` in the current working directory
3. `~/Library/Application Support/token-control-monitor/.env`

Required when using the Arkham intelligence provider:

- `ARKHAM_API_KEY`

Required for monitor install and alerting:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

If a user wants unattended launchd monitoring, prefer copying or syncing the working `.env` into the Application Support location so the LaunchAgent can read it reliably.

## Workflow Hints

- For analysis requests, summarize the script output in plain language instead of dumping raw JSON unless the user asked for raw output.
- For ambiguous token resolution, show the top candidates and ask the user to choose.
- For deployment requests, validate the token first with `token-report` or `resolve-token` before installing the monitor.
- For “what is running now?” questions, prefer `monitor status` and `monitor logs`.

## References

- Invocation examples: [references/invocation-patterns.md](references/invocation-patterns.md)
- Config and secrets: [references/config-and-secrets.md](references/config-and-secrets.md)
- macOS launchd behavior: [references/launchd.md](references/launchd.md)
