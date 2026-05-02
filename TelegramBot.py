#!/usr/bin/env python3
"""
Telegram Bot 推送模块
"""
from dotenv import load_dotenv
import requests


load_dotenv()


def send_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown"):
    """
    发送 Telegram 消息

    Args:
        bot_token: 你的 Telegram Bot Token（找 @BotFather 获取）
        chat_id: 目标 Chat ID（用户 ID 或 群组 ID）
        text: 消息内容（支持 Markdown）
        parse_mode: "Markdown" 或 "HTML"
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as exc:
        print(f"[Telegram Error] 请求失败: {exc}")
        return False
    except ValueError as exc:
        print(f"[Telegram Error] 响应不是有效 JSON: {exc}")
        return False

    if not result.get("ok"):
        print(f"[Telegram Error] {result}")
        return False
    return True


def main():
    # 测试推送
    import os
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")
        return

    test_msg = (
        "🐾 *Token Monitor 已上线*\n\n"
        "Token Control Monitor 服务启动成功\n"
        "监控阈值: $10,000+\n"
        "模式: 轮询 (60s)"
    )
    send_message(bot_token, chat_id, test_msg)


if __name__ == "__main__":
    main()
