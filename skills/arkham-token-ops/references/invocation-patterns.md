# Invocation Patterns

Use the skill through natural language, then map the request to the CLI.

## Common mappings

### Token overview

User intent:

- “分析某个代币的链上情况”
- “帮我看这个 token 的大户和最近转账”

Preferred flow:

1. If only a symbol/query is given, run `resolve-token`
2. If resolved, run `token-report`
3. Summarize the result in plain language

Commands:

```bash
python3 scripts/arkham_token_ops.py resolve-token --query TOKEN_SYMBOL
python3 scripts/arkham_token_ops.py token-report --chain ethereum --token-address 0xYOUR_TOKEN_ADDRESS
```

### Address analysis

User intent:

- “分析这个地址”
- “看看这个地址是不是某个实体”

Command:

```bash
python3 scripts/arkham_token_ops.py address-report --chain ethereum --address 0x...
```

### Recent or large transfers

User intent:

- “看看某个代币最近的大额转账”
- “给我最近 24 小时超过 1 万美金的转账”

Command:

```bash
python3 scripts/arkham_token_ops.py recent-transfers --chain ethereum --token-address 0x... --usd-gte 10000 --limit 20
```

### Deploy monitoring

User intent:

- “把这个 token 监控部署到一台长期运行的 macOS 设备”
- “长期监控这个 token，超过 5000 美金就提醒”

Flow:

1. Confirm explicit `chain + token address`
2. Validate token with `token-report` if needed
3. Install with `monitor install`
4. Confirm with `monitor status`

Commands:

```bash
python3 scripts/arkham_token_ops.py monitor install --name token-main --chain ethereum --token-address 0x... --threshold-usd 5000 --interval-sec 60
python3 scripts/arkham_token_ops.py monitor status --name token-main
```

## Ambiguity handling

- If symbol resolution returns multiple candidates, show the candidates and ask the user to pick one.
- Do not deploy from a fuzzy symbol-only query when the result is ambiguous.
- If the user omits the chain for address analysis and the network is not obvious, ask for the chain first.
