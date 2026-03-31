# Arkham Token Monitor And Skill

该仓库提供两套可组合使用的能力：

1. 面向单一目标代币的原始监控脚本，适合直接运行 `monitor.py`
2. 可复用的 `arkham-token-ops` skill，适合安装到 Codex / OpenClaw，用于通用 token 分析、地址分析以及 macOS `launchd` 常驻监控

如果你的目标是快速接入单一代币监控，可以直接使用原始脚本。
如果你需要支持更多 token、进行地址画像分析，或希望安装 skill 后即可直接通过自然语言进行调用，建议优先使用 `skills/arkham-token-ops/`。

---

## 功能概览

| 能力 | 入口 | 适用场景 |
|------|------|----------|
| 目标代币一次性报告 | `monitor.py --mode report` | 快速查看指定代币的基础信息、持仓与近期转账 |
| 目标代币轮询监控 | `monitor.py --mode poll` | 持续监控指定代币并发送 Telegram 告警 |
| 通用 token 分析 | `skills/arkham-token-ops/scripts/arkham_token_ops.py` | 分析任意 token、地址，以及近期或大额转账 |
| macOS 常驻监控 | `arkham-token-ops monitor install` | 在 macOS 上通过 `launchd` 长期运行监控 |
| Codex / OpenClaw skill | `skills/arkham-token-ops/` | 安装 skill 后即可直接通过自然语言进行调用 |

---

## 仓库结构

```text
project-root/
├── monitor.py                       # 原始目标代币监控脚本
├── TelegramBot.py                   # Telegram 推送模块
├── requirements.txt                 # 原始脚本依赖
├── .env.example                     # 环境变量模板
├── deploy/token-monitor.service     # Linux systemd 示例
├── skills/
│   └── arkham-token-ops/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       ├── scripts/arkham_token_ops.py
│       ├── scripts/lib/
│       └── references/
└── README.md
```

---

## 方案选择

### 方案 A：使用原始目标代币脚本

适合：

- 只监控某一个代币
- 不需要 skill 安装
- 希望快速通过 Python 脚本接入 Telegram 告警

### 方案 B：使用 `arkham-token-ops` skill

适合：

- 需要分析多个 token，而不局限于单一资产
- 需要查看链上地址画像与资金流向
- 需要在 macOS 设备上长期运行监控
- 需要在 Codex / OpenClaw 中通过自然语言调用相关能力

---

## 快速开始

### 1. 安装 Python 依赖

原始脚本与 skill 都依赖 Arkham API 和 Telegram，建议先准备 Python 虚拟环境：

```bash
cd your-project-dir
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

`.env` 至少需要包含以下变量：

```env
ARKHAM_API_KEY=your_arkham_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

说明：

- `ARKHAM_API_KEY`：所有 Arkham 分析和监控都需要
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：告警推送和 `monitor install` 需要

如果需要通过 macOS `launchd` 长期运行，建议将同样的变量同步到：

```text
~/Library/Application Support/arkham-token-ops/.env
```

---

## 原始目标代币脚本用法

### 一次性报告

```bash
python3 monitor.py --mode report
```

输出内容包括：

- 目标代币基本信息
- 相关实体
- Top holders
- 最近 24h 转账概况

### 轮询监控

```bash
python3 monitor.py --mode poll
python3 monitor.py --mode poll --threshold 5000 --interval 30
```

### WebSocket 实时流

> Arkham 对 WebSocket 订阅通常有较高金额门槛。常规场景下更推荐使用 `poll`。

```bash
python3 monitor.py --mode websocket
```

---

## Arkham Token Ops Skill

`skills/arkham-token-ops/` 是该仓库中更通用、也更适合复用的能力层。

主要支持：

- token 分析
- 地址分析
- 最近 / 大额转账分析
- Telegram 告警
- 在 macOS 上通过 `launchd` 部署常驻监控

主入口如下：

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py --help
```

### 常用命令

#### 1. 分析 token

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py \
  token-report \
  --chain ethereum \
  --token-address 0xYOUR_TOKEN_ADDRESS
```

#### 2. 分析地址

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py \
  address-report \
  --chain ethereum \
  --address 0xYOUR_ADDRESS
```

#### 3. 查看近期 / 大额转账

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py \
  recent-transfers \
  --chain ethereum \
  --token-address 0xYOUR_TOKEN_ADDRESS \
  --usd-gte 10000 \
  --limit 20
```

#### 4. 通过符号名解析 token

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py \
  resolve-token \
  --query TOKEN_SYMBOL
```

说明：

- 如果一个 token 是多链资产，`resolve-token` 可能返回 `ambiguous`
- 在这种情况下，建议显式指定 `chain + token address`
- 对监控部署场景，始终建议显式提供 `chain + token address`

---

## 在 Codex / OpenClaw 中安装 Skill

仓库已内置安装器，可用于快速安装该 skill。

### 方式 A：仓库内一键安装

如果已经获取该仓库，并希望避免手动复制目录，可以直接运行：

```bash
python3 scripts/install_skill.py
```

或者：

```bash
bash scripts/install_skill.sh
```

默认安装路径为：

```text
~/.codex/skills/arkham-token-ops
```

如果环境中设置了自定义 `CODEX_HOME`，安装器会优先写入：

```text
$CODEX_HOME/skills/arkham-token-ops
```

可选参数：

```bash
python3 scripts/install_skill.py --force
python3 scripts/install_skill.py --dest-root /path/to/skills
python3 scripts/install_skill.py --link
```

参数说明：

- `--force`：覆盖已有安装
- `--dest-root`：指定 skills 根目录
- `--link`：创建符号链接，适合开发场景下保持仓库修改实时生效

### 方式 B：手动复制

如果希望手动完成安装，也可以直接复制 skill 目录：

```bash
cp -R skills/arkham-token-ops ~/.codex/skills/
```

### 方式 C：从 GitHub skill 路径安装

如果 Codex / OpenClaw 支持按 GitHub skill URL 安装，也可以直接使用：

```text
https://github.com/<owner>/<repo>/tree/<branch>/skills/arkham-token-ops
```

如果仓库为私有仓库，需要确保对应 GitHub 账号已具备读取权限。

安装完成后，建议重启 Codex / OpenClaw 以重新加载技能列表。

重启后即可通过自然语言调用，例如：

- `Use $arkham-token-ops to analyze a token on Ethereum`
- `Use $arkham-token-ops to inspect this address on Ethereum: 0x...`
- `Use $arkham-token-ops to deploy a token transfer monitor on macOS`

skill 说明文件位于：

- `skills/arkham-token-ops/SKILL.md`

---

## macOS 常驻监控

`arkham-token-ops` 默认使用 per-user `LaunchAgent`，适合部署到 Mac mini 等长期运行的 macOS 设备。

### 安装一个监控

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py \
  monitor install \
  --name token-main \
  --chain ethereum \
  --token-address 0xYOUR_TOKEN_ADDRESS \
  --threshold-usd 5000 \
  --interval-sec 60
```

### 查看状态

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py monitor status --name token-main
```

### 查看日志

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py monitor logs --name token-main
```

### 停止监控

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py monitor stop --name token-main
```

### 删除监控

```bash
python3 skills/arkham-token-ops/scripts/arkham_token_ops.py monitor uninstall --name token-main
```

默认路径如下：

- plist:
  `~/Library/LaunchAgents/com.codex.arkham-token-monitor.<name>.plist`
- 监控状态:
  `~/Library/Application Support/arkham-token-ops/monitors/<name>/`
- 日志:
  `~/Library/Logs/arkham-token-ops/<name>.log`
  `~/Library/Logs/arkham-token-ops/<name>.err.log`

---

## Linux 部署

如果需要在 Linux 服务器上运行旧版目标代币监控脚本，可以继续使用 `systemd`。

示例服务文件位于：

- `deploy/token-monitor.service`

基本流程：

```bash
scp -r your-project-dir user@your-server:/home/user/
ssh user@your-server
cd /home/user/your-project-dir
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

随后将 `deploy/token-monitor.service` 中的路径替换为实际服务器路径并启用即可。

---

## 常见问题

**Q: 为什么 `resolve-token` 没有直接替我选链？**

因为部分代币在 Arkham 中同时存在多链资产映射。分析时可以先查看候选结果，再明确指定目标链；部署监控时必须显式提供 `chain + token address`，以确保结果准确且可控。

**Q: Telegram 是不是已经变成可以聊天问答的 bot？**

不是。当前 Telegram 仅用于接收告警，分析结果主要通过 Codex / OpenClaw 或命令行返回。

**Q: 现在最推荐的入口是什么？**

如果希望长期维护并扩展该项目，最推荐的入口是 `skills/arkham-token-ops/`。原始 `monitor.py` 更适合作为面向单一目标代币的轻量脚本保留。

**Q: Trial API 的 datapoints 会不会很快用完？**

会。无论是旧版轮询还是 skill 的持续监控，本质上都会持续调用 Arkham API。建议：

- 只监控你真的关心的 token
- 合理提高 `interval-sec`
- 先用较高阈值观察，再逐步下调
- 如果需要长期运行，提前准备更稳定的 Arkham 配额

**Q: 如何兼容其他 token？**

使用 `arkham-token-ops` 的 `token-report`、`recent-transfers` 和 `monitor install`，将示例地址替换为目标 token 地址即可。

---

## 后续可扩展方向

- [ ] 增加更好的 token resolve 交互输出
- [ ] 增加 Arkham `429` / `5xx` 的重试退避
- [ ] 增加监控状态摘要命令
- [ ] 增加 Docker 化部署方案
