# Config And Secrets

The skill reads configuration in this order:

1. Process environment variables
2. `.env` in the current working directory
3. `~/Library/Application Support/arkham-token-ops/.env`

## Required variables

Always required:

```env
ARKHAM_API_KEY=...
```

Required for monitoring and Telegram alerts:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Recommended macOS setup

For one-off local analysis, a project-local `.env` is fine.

For unattended `launchd` monitors, prefer keeping secrets in:

```text
~/Library/Application Support/arkham-token-ops/.env
```

The `monitor install` command syncs the resolved keys into that location so the LaunchAgent can keep working after the original shell exits.

## Security notes

- Do not store secrets in `SKILL.md`
- Do not commit secrets into a shared repo
- Rotate Telegram and Arkham credentials if they were ever exposed in chat or version control
