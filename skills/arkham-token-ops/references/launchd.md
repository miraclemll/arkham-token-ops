# macOS Launchd Notes

This skill deploys monitors as per-user LaunchAgents.

## Paths

- Plist:
  `~/Library/LaunchAgents/com.codex.arkham-token-monitor.<name>.plist`
- Monitor state:
  `~/Library/Application Support/arkham-token-ops/monitors/<name>/`
- Logs:
  `~/Library/Logs/arkham-token-ops/<name>.log`
  `~/Library/Logs/arkham-token-ops/<name>.err.log`

## Management commands

Install:

```bash
python3 scripts/arkham_token_ops.py monitor install --name example --chain ethereum --token-address 0x... --threshold-usd 5000 --interval-sec 60
```

Inspect:

```bash
python3 scripts/arkham_token_ops.py monitor status --name example
python3 scripts/arkham_token_ops.py monitor logs --name example
```

Stop:

```bash
python3 scripts/arkham_token_ops.py monitor stop --name example
```

Remove:

```bash
python3 scripts/arkham_token_ops.py monitor uninstall --name example
```

## Runtime behavior

- REST polling is the default monitor mode
- The monitor seeds its dedupe cache on first run so it does not replay old transfers
- Dedupe state is stored on disk so restarts do not resend already-seen transactions
- If Arkham or Telegram fails, the runtime records the last error in the monitor state file
