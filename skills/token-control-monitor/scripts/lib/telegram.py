#!/usr/bin/env python3
"""Telegram helpers for Token Control Monitor."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request
from typing import Dict, Optional

from .arkham_client import shorten_label


EXPLORER_BASE = {
    "ethereum": "https://etherscan.io/tx/",
    "arbitrum": "https://arbiscan.io/tx/",
    "optimism": "https://optimistic.etherscan.io/tx/",
    "base": "https://basescan.org/tx/",
    "polygon": "https://polygonscan.com/tx/",
    "bsc": "https://bscscan.com/tx/",
    "avalanche": "https://snowtrace.io/tx/",
}


def format_usd(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.2f}K"
    return f"${amount:.2f}"


def transfer_alert_message(transfer: Dict[str, object], token_name: str, token_symbol: str) -> str:
    symbol = html.escape(token_symbol or token_name or "TOKEN")
    from_label = html.escape(
        shorten_label(str(transfer.get("from_label") or transfer.get("from_entity") or ""), str(transfer.get("from_address") or ""))
    )
    to_label = html.escape(
        shorten_label(str(transfer.get("to_label") or transfer.get("to_entity") or ""), str(transfer.get("to_address") or ""))
    )
    timestamp = html.escape(str(transfer.get("timestamp") or ""))
    amount_text = html.escape(format_usd(float(transfer.get("amount_usd") or 0)))
    tx_hash = str(transfer.get("tx_hash") or "")
    chain = str(transfer.get("blockchain") or "").lower()
    explorer = EXPLORER_BASE.get(chain)
    explorer_line = ""
    if explorer and tx_hash:
        explorer_line = f"\n🔗 <a href=\"{html.escape(explorer + tx_hash)}\">查看交易</a>"

    return (
        f"🐋 <b>{symbol} 大额转账预警</b>\n\n"
        f"💰 金额: <b>{amount_text}</b>\n"
        f"📤 From: <code>{from_label}</code>\n"
        f"📥 To: <code>{to_label}</code>\n"
        f"⏱️ {timestamp}"
        f"{explorer_line}"
    )


def send_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> Dict[str, object]:
    if not bot_token or not chat_id:
        raise RuntimeError("Missing Telegram bot token or chat id.")

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram API connection failed: {exc.reason}") from exc

    result = json.loads(body)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected the message: {result}")
    return result
