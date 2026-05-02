#!/usr/bin/env python3
"""
Token Control Monitor - Target Token Monitor
实时监控目标代币的大额转账，通过 Telegram 推送预警
"""

import os
import json
import ssl
import html
import asyncio
from collections import deque
from datetime import datetime

import requests
import websockets
from dotenv import load_dotenv

import TelegramBot

# =====================
# 配置区
# =====================
load_dotenv()

API_KEY = os.getenv("ARKHAM_API_KEY", "")

# 目标代币配置
TARGET_TOKEN_ADDRESS = os.getenv("TARGET_TOKEN_ADDRESS", "0xYOUR_TOKEN_ADDRESS")
TARGET_CHAIN = os.getenv("TARGET_CHAIN", "ethereum")
TARGET_TOKEN_NAME = os.getenv("TARGET_TOKEN_NAME", "Target Token")
TARGET_TOKEN_QUERY = os.getenv("TARGET_TOKEN_QUERY", TARGET_TOKEN_NAME)

# 监控阈值 (USD)
# Arkham WebSocket 最小 usdGte = 10,000,000 (1000万) 才能订阅
# 我们用 REST API 轮询查 recent transfers 来抓中小额
USD_THRESHOLD = 10_000  # 触发预警的 USD 阈值（$10k 以上）

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# API 配置
BASE_URL = "https://api.arkm.com"
HEADERS = {"API-Key": API_KEY} if API_KEY else {}
REQUEST_TIMEOUT = 15
TRACKED_TX_CACHE_SIZE = 1000


# =====================
# 工具函数
# =====================

def format_usd(amount: float) -> str:
    """格式化 USD 金额"""
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.2f}K"
    else:
        return f"${amount:.2f}"


def parse_transfer(transfer: dict) -> dict:
    """解析转账记录，提取关键信息"""
    from_data = transfer.get("from", {}) or transfer.get("fromAddress", {}) or {}
    to_data = transfer.get("to", {}) or transfer.get("toAddress", {}) or {}
    from_entity = from_data.get("entity", "") or from_data.get("arkhamEntity", "")
    to_entity = to_data.get("entity", "") or to_data.get("arkhamEntity", "")
    from_label = from_data.get("label", "") or from_data.get("arkhamLabel", "") or from_data.get("name", "")
    to_label = to_data.get("label", "") or to_data.get("arkhamLabel", "") or to_data.get("name", "")

    if isinstance(from_entity, dict):
        from_entity = from_entity.get("name", "")
    if isinstance(to_entity, dict):
        to_entity = to_entity.get("name", "")
    if isinstance(from_label, dict):
        from_label = from_label.get("name", "")
    if isinstance(to_label, dict):
        to_label = to_label.get("name", "")

    return {
        "tx_hash": transfer.get("txHash", "") or transfer.get("transactionHash", "") or transfer.get("id", ""),
        "blockchain": transfer.get("blockchain", "") or transfer.get("chain", ""),
        "from_address": from_data.get("address", ""),
        "from_entity": from_entity,
        "from_label": from_label,
        "to_address": to_data.get("address", ""),
        "to_entity": to_entity,
        "to_label": to_label,
        "amount": float(transfer.get("amount", 0) or transfer.get("unitValue", 0) or 0),
        "amount_usd": float(transfer.get("amountUSD", 0) or transfer.get("historicalUSD", 0) or 0),
        "timestamp": transfer.get("timestamp", "") or transfer.get("blockTimestamp", ""),
        "token_symbol": transfer.get("token", {}).get("symbol", "") or transfer.get("tokenSymbol", ""),
    }


def shorten_label(label: str, fallback: str, width: int = 10) -> str:
    """返回适合日志展示的简短标签。"""
    if label:
        return label
    return f"{fallback[:width]}..." if fallback else "Unknown"


def build_telegram_message(transfer: dict) -> str:
    """构建 Telegram HTML 消息，避免 Markdown 转义问题。"""
    from_label = html.escape(shorten_label(
        transfer["from_label"] or transfer["from_entity"], transfer["from_address"]
    ))
    to_label = html.escape(shorten_label(
        transfer["to_label"] or transfer["to_entity"], transfer["to_address"]
    ))
    timestamp = html.escape(transfer["timestamp"])
    tx_hash = html.escape(transfer["tx_hash"])

    return (
        f"🐋 <b>{html.escape(TARGET_TOKEN_NAME)} 大额转账预警</b>\n\n"
        f"💰 金额: <b>{html.escape(format_usd(transfer['amount_usd']))}</b>\n"
        f"📤 From: <code>{from_label}</code>\n"
        f"📥 To: <code>{to_label}</code>\n"
        f"⏱️ {timestamp}\n"
        f"🔗 <a href=\"https://etherscan.io/tx/{tx_hash}\">查看交易</a>"
    )


def ensure_required_config(require_telegram: bool = False):
    """启动前做基础配置校验。"""
    if not API_KEY:
        raise SystemExit("缺少 ARKHAM_API_KEY。请先复制 .env.example 为 .env 并填写配置。")
    if not TARGET_TOKEN_ADDRESS or TARGET_TOKEN_ADDRESS == "0xYOUR_TOKEN_ADDRESS":
        raise SystemExit("缺少 TARGET_TOKEN_ADDRESS。请在 .env 中填写要监控的代币合约地址。")
    if require_telegram and (not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID):
        print("⚠️ 未配置 Telegram，程序会继续运行，但不会发送告警消息。")


# =====================
# REST API 调用
# =====================

def get_token_info():
    """获取目标代币基本信息"""
    url = f"{BASE_URL}/intelligence/token/{TARGET_CHAIN}/{TARGET_TOKEN_ADDRESS}"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_token_price_history(days: int = 7):
    """获取目标代币价格历史"""
    url = f"{BASE_URL}/token/price/history/{TARGET_CHAIN}/{TARGET_TOKEN_ADDRESS}"
    params = {"timeStart": f"{days}d"}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_recent_transfers(limit: int = 50):
    """
    获取目标代币最近转账记录（REST 轮询模式）
    timeLast: 1h, 6h, 24h, 7d
    """
    url = f"{BASE_URL}/transfers"
    params = {
        "tokens": TARGET_TOKEN_ADDRESS,
        "chains": TARGET_CHAIN,
        "timeLast": "24h",
        "limit": limit,
        "sortKey": "time",
        "sortDir": "desc",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_address_intelligence(address: str):
    """查询地址情报（实体、标签、归属）"""
    url = f"{BASE_URL}/intelligence/address/{address}"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_entity_intelligence(entity: str):
    """查询实体情报"""
    url = f"{BASE_URL}/intelligence/entity/{entity}"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_token_holders(top: int = 20):
    """获取目标代币前 N 大持有者"""
    url = f"{BASE_URL}/token/holders/{TARGET_CHAIN}/{TARGET_TOKEN_ADDRESS}"
    params = {"limit": top}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def search_token_entities():
    """搜索目标代币相关实体（交易所、鲸鱼等）"""
    url = f"{BASE_URL}/intelligence/search"
    params = {"query": TARGET_TOKEN_QUERY, "filterLimits": json.dumps({"arkhamEntities": 10, "tokens": 5})}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# =====================
# WebSocket 实时流
# =====================

async def stream_transfers_websocket(usd_gte: int = 10_000_000):
    """
    WebSocket 实时监控目标代币转账
    注意: Arkham 要求 usdGte >= 10,000,000 (1000万USD) 才能订阅
    """
    url = "wss://api.arkm.com/ws/transfers"
    headers = {"API-Key": API_KEY}

    ssl_context = ssl.create_default_context()

    async with websockets.connect(url, additional_headers=headers, ssl=ssl_context) as ws:
        subscribe_msg = {
            "subscribe": True,
            "tokens": [TARGET_TOKEN_ADDRESS],
            "usdGte": usd_gte,  # 最小 10M USD
        }
        await ws.send(json.dumps(subscribe_msg))
        print(f"[{datetime.now().isoformat()}] ✅ WebSocket 已连接，监控 {TARGET_TOKEN_NAME} 转账 (≥${usd_gte/1_000_000}M)")

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                data = json.loads(msg)
                await handle_websocket_message(data)
            except asyncio.TimeoutError:
                # 发送心跳
                await ws.ping()
                print(f"[{datetime.now().isoformat()}] 💓 WebSocket 心跳正常")


async def handle_websocket_message(data: dict):
    """处理 WebSocket 推送的消息"""
    try:
        transfer = data.get("transfer", {})
        if not transfer:
            return

        t = parse_transfer(transfer)
        amount_usd = t["amount_usd"]

        from_label = shorten_label(t["from_label"] or t["from_entity"], t["from_address"])
        to_label = shorten_label(t["to_label"] or t["to_entity"], t["to_address"])

        print(f"\n{'='*50}")
        print(f"🚨 检测到大额 {TARGET_TOKEN_NAME} 转账!")
        print(f"   金额: {format_usd(amount_usd)}")
        print(f"   From: {from_label}")
        print(f"   To: {to_label}")
        print(f"{'='*50}\n")

        # 发送到 Telegram
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            TelegramBot.send_message(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                build_telegram_message(t),
                parse_mode="HTML",
            )

    except Exception as e:
        print(f"[ERROR] 处理 WebSocket 消息失败: {e}")


# =====================
# 轮询模式（替代 WebSocket 的轻量方案）
# =====================

async def poll_transfers_loop(interval_seconds: int = 60):
    """
    轮询模式：每 N 秒查一次最近转账
    适合 Trial 版（datapoints 有限），比 WebSocket 消耗更少
    """
    if interval_seconds <= 0:
        raise ValueError("轮询间隔必须大于 0 秒")

    print(f"[{datetime.now().isoformat()}] 🔄 启动轮询模式，间隔 {interval_seconds} 秒")
    seen_tx_hashes = deque(maxlen=TRACKED_TX_CACHE_SIZE)

    try:
        initial_data = get_recent_transfers(limit=50)
        initial_transfers = initial_data.get("transfers", [])
        for transfer in initial_transfers:
            tx_hash = transfer.get("txHash")
            if tx_hash:
                seen_tx_hashes.append(tx_hash)
        print(f"[{datetime.now().isoformat()}] 已建立初始基线，忽略启动前的 {len(initial_transfers)} 条历史转账")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ⚠️ 初始化基线失败，将在下一轮重试: {e}")

    while True:
        try:
            data = get_recent_transfers(limit=50)
            transfers = data.get("transfers", [])

            if not transfers:
                await asyncio.sleep(interval_seconds)
                continue

            known_hashes = set(seen_tx_hashes)
            new_transfers = [
                transfer for transfer in transfers
                if transfer.get("txHash") and transfer.get("txHash") not in known_hashes
            ]

            if new_transfers:
                print(f"[{datetime.now().isoformat()}] 发现 {len(new_transfers)} 条新转账")

                for t in reversed(new_transfers):  # 正序处理（从旧到新）
                    parsed = parse_transfer(t)
                    if parsed["amount_usd"] >= USD_THRESHOLD:
                        from_label = shorten_label(
                            parsed["from_label"] or parsed["from_entity"], parsed["from_address"]
                        )
                        to_label = shorten_label(
                            parsed["to_label"] or parsed["to_entity"], parsed["to_address"]
                        )

                        print(f"   🚨 {format_usd(parsed['amount_usd'])} | {from_label} → {to_label}")

                        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                            TelegramBot.send_message(
                                TELEGRAM_BOT_TOKEN,
                                TELEGRAM_CHAT_ID,
                                build_telegram_message(parsed),
                                parse_mode="HTML",
                            )

            for transfer in transfers:
                tx_hash = transfer.get("txHash")
                if tx_hash and tx_hash not in known_hashes:
                    seen_tx_hashes.append(tx_hash)

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ❌ 轮询异常: {e}")

        await asyncio.sleep(interval_seconds)


# =====================
# 一次性报告
# =====================

def generate_token_report():
    """生成目标代币情报报告（一次性查询）"""
    print("=" * 60)
    print(f"📊 {TARGET_TOKEN_NAME} 代币情报报告")
    print("=" * 60)

    # 1. Token 基本信息
    print("\n[1] Token 信息")
    print("-" * 40)
    try:
        token_info = get_token_info()
        print(json.dumps(token_info, indent=2, ensure_ascii=False)[:2000])
    except Exception as e:
        print(f"❌ 获取 Token 信息失败: {e}")

    # 2. 搜索目标代币相关实体
    print(f"\n[2] {TARGET_TOKEN_NAME} 相关实体")
    print("-" * 40)
    try:
        entities = search_token_entities()
        print(json.dumps(entities, indent=2, ensure_ascii=False)[:2000])
    except Exception as e:
        print(f"❌ 搜索实体失败: {e}")

    # 3. Top Holders
    print("\n[3] 前 20 大持有者")
    print("-" * 40)
    try:
        holders = get_token_holders(top=20)
        print(json.dumps(holders, indent=2, ensure_ascii=False)[:3000])
    except Exception as e:
        print(f"❌ 获取持有者失败: {e}")

    # 4. 最近 24h 转账概况
    print("\n[4] 最近 24h 转账记录")
    print("-" * 40)
    try:
        transfers = get_recent_transfers(limit=20)
        t_list = transfers.get("transfers", [])
        print(f"共 {len(t_list)} 条转账记录")

        # 按 USD 金额排序
        sorted_tx = sorted(t_list, key=lambda x: float(x.get("amountUSD", 0)), reverse=True)
        for i, t in enumerate(sorted_tx[:10], 1):
            parsed = parse_transfer(t)
            from_lbl = parsed["from_label"] or parsed["from_entity"] or parsed["from_address"][:8]
            to_lbl = parsed["to_label"] or parsed["to_entity"] or parsed["to_address"][:8]
            print(f"  {i}. {format_usd(parsed['amount_usd']):>10} | {from_lbl[:15]:<15} → {to_lbl[:15]}")

    except Exception as e:
        print(f"❌ 获取转账记录失败: {e}")

    print("\n" + "=" * 60)


# =====================
# 入口
# =====================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Token Control Monitor")
    parser.add_argument("--mode", choices=["report", "poll", "websocket"],
                        default="report", help="运行模式")
    parser.add_argument("--interval", type=int, default=60,
                        help="轮询间隔（秒），仅 poll 模式有效")
    parser.add_argument("--threshold", type=int, default=10000,
                        help="USD 预警阈值，默认 $10,000")
    args = parser.parse_args()

    global USD_THRESHOLD
    USD_THRESHOLD = args.threshold

    if args.mode == "report":
        ensure_required_config()
        generate_token_report()

    elif args.mode == "poll":
        ensure_required_config(require_telegram=True)
        asyncio.run(poll_transfers_loop(interval_seconds=args.interval))

    elif args.mode == "websocket":
        # WebSocket 需要 usdGte >= 10M
        ensure_required_config(require_telegram=True)
        print("⚠️ WebSocket 模式要求 usdGte >= $10,000,000")
        print("   建议使用 poll 模式监控小额更灵活")
        asyncio.run(stream_transfers_websocket())


if __name__ == "__main__":
    main()
