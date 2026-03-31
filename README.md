# Arkham Token Monitor And Skill

这个仓库现在包含两套能力：

1. 一个原始的目标代币监控脚本项目，适合直接运行 `monitor.py`
2. 一个可复用的 `arkham-token-ops` skill，适合安装到 Codex / OpenClaw，在 macOS 上做通用 token 分析、监控和 `launchd` 部署

如果你只是想快速监控某个目标代币，可以用旧脚本。
如果你想兼容其他代币、做地址分析、或者让同事在 Codex 里直接调用，优先使用 `skills/arkham-token-ops/`。

---

## 功能概览

| 能力 | 入口 | 适用场景 |
|------|------|----------|
| 目标代币一次性报告 | `monitor.py --mode report` | 快速查看某个代币的 token 信息、持仓和最近转账 |
| 目标代币轮询监控 | `monitor.py --mode poll` | 持续监控某个代币并推送 Telegram |
| 通用 token 分析 | `skills/arkham-token-ops/scripts/arkham_token_ops.py` | 分析任意 token、地址、最近或大额转账 |
| macOS 常驻监控 | `arkham-token-ops monitor install` | 在 Mac mini 上通过 `launchd` 长期运行 |
| Codex / OpenClaw skill | `skills/arkham-token-ops/` | 让其他同事安装 skill 后直接自然语言调用 |

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

### 方案 A：继续用原始目标代币脚本

适合：

- 只监控某一个代币
- 不需要 skill 安装
- 想快速用 Python 脚本起一个 Telegram 提醒

### 方案 B：使用 `arkham-token-ops` skill

适合：

- 想分析其他 token，不局限于单个代币
- 想看链上地址画像
- 想在 Mac mini 上长期运行监控
- 想让 Codex / OpenClaw 通过自然语言调用能力

---

## 快速开始

### 1. 安装 Python 依赖

原始脚本和 skill 都依赖 Arkham API 与 Telegram，所以建议先准备一个 Python 虚拟环境：

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

`.env` 最少需要：

```env
ARKHAM_API_KEY=your_arkham_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

说明：

- `ARKHAM_API_KEY`：所有 Arkham 分析和监控都需要
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：只有告警推送和 monitor install 需要

如果是给 macOS `launchd` 长期运行，推荐把同样的变量也放到：

```text
~/Library/Application Support/arkham-token-ops/.env
```

---

## 原始目标代币脚本用法

### 一次性报告

```bash
python3 monitor.py --mode report
```

输出包括：

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

> Arkham 对 websocket 订阅有较高金额门槛。常规场景更推荐 `poll`。

```bash
python3 monitor.py --mode websocket
```

---

## Arkham Token Ops Skill

`skills/arkham-token-ops/` 是这个仓库里更通用的能力层。

它支持：

- token 分析
- 地址分析
- 最近 / 大额转账分析
- Telegram 告警
- 在 macOS 上通过 `launchd` 部署常驻监控

主入口：

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

#### 3. 查看最近 / 大额转账

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

注意：

- 如果一个 token 是多链资产，`resolve-token` 可能返回 `ambiguous`
- 这种情况下请显式指定 `chain + token address`
- 对部署监控来说，永远建议显式提供 `chain + token address`

---

## 在 Codex / OpenClaw 中安装 Skill

如果你的 Codex skills 目录是默认位置，可以直接把这个 skill 复制进去：

```bash
cp -R skills/arkham-token-ops ~/.codex/skills/
```

安装后建议重启 Codex，让它重新加载技能列表。

重启后可以自然语言调用，例如：

- `Use $arkham-token-ops to analyze a token on Ethereum`
- `Use $arkham-token-ops to inspect this address on Ethereum: 0x...`
- `Use $arkham-token-ops to deploy a token transfer monitor on macOS`

skill 说明文件在：

- `skills/arkham-token-ops/SKILL.md`

---

## macOS 常驻监控

`arkham-token-ops` 默认使用 per-user `LaunchAgent`，适合部署到 Mac mini。

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

默认路径：

- plist:
  `~/Library/LaunchAgents/com.codex.arkham-token-monitor.<name>.plist`
- 监控状态:
  `~/Library/Application Support/arkham-token-ops/monitors/<name>/`
- 日志:
  `~/Library/Logs/arkham-token-ops/<name>.log`
  `~/Library/Logs/arkham-token-ops/<name>.err.log`

---

## Linux 部署

如果你还是要在 Linux 服务器上跑旧版目标代币监控脚本，可以继续用 `systemd`。

示例服务文件见：

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

然后把 `deploy/token-monitor.service` 里的路径替换为实际服务器路径后启用。

---

## 常见问题

**Q: 为什么 `resolve-token` 没有直接替我选链？**

因为有些代币在 Arkham 里是多链资产。分析时可以先看候选，再明确指定你要的链；部署监控时必须显式给出 `chain + token address`，这样更安全。

**Q: Telegram 是不是已经变成可以聊天问答的 bot？**

不是。当前 Telegram 仍然只负责接收告警，分析结果主要在 Codex / OpenClaw 或命令行里返回。

**Q: 现在最推荐的入口是什么？**

如果你在持续维护这个项目，最推荐的是 `skills/arkham-token-ops/`。原始 `monitor.py` 更适合作为某个目标代币专用、轻量脚本保留。

**Q: Trial API 的 datapoints 会不会很快用完？**

会。无论是旧版轮询还是 skill 的持续监控，本质上都会持续调用 Arkham API。建议：

- 只监控你真的关心的 token
- 合理提高 `interval-sec`
- 先用较高阈值观察，再逐步下调
- 如果是长期运行，准备更稳定的 Arkham 配额

**Q: 如何兼容其他 token？**

用 `arkham-token-ops` 的 `token-report`、`recent-transfers` 和 `monitor install`，把示例地址替换成你自己的 token 地址即可。

---

## 后续可扩展方向

- [ ] 给 skill 增加安装脚本，方便在其他机器一键安装
- [ ] 增加更好的 token resolve 交互输出
- [ ] 增加 Arkham `429` / `5xx` 的重试退避
- [ ] 增加监控状态摘要命令
- [ ] 增加 Docker 化部署方案
