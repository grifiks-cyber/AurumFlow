"""
Aurum Flow — Get Your Chat ID
Run this ONCE to get your numeric chat_id for TIKTOK_REVIEW_CHAT.

Steps:
  1. Run: python get_my_chat_id.py
  2. Open Telegram and send ANY message to your AurumFlow bot
  3. Your chat_id will appear here in the terminal
  4. Copy it into .env: TIKTOK_REVIEW_CHAT=YOUR_NUMBER
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found in .env")
    sys.exit(1)


async def main():
    from telegram import Bot
    from telegram.error import TelegramError

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()

    print("=" * 50)
    print(f"  AurumFlow Bot: @{me.username}")
    print("=" * 50)
    print()
    print("👉 Now open Telegram and send ANY message to:")
    print(f"   @{me.username}")
    print()
    print("Waiting for your message (30 seconds)...")
    print()

    # Poll for updates
    last_update_id = None
    for i in range(30):
        try:
            updates = await bot.get_updates(
                offset=last_update_id,
                timeout=1,
                allowed_updates=["message"],
            )
            for update in updates:
                last_update_id = update.update_id + 1
                if update.message:
                    user = update.message.from_user
                    chat_id = update.message.chat_id
                    print("=" * 50)
                    print(f"  ✅ Message received!")
                    print(f"  From: {user.first_name} (@{user.username})")
                    print(f"  Your chat_id: {chat_id}")
                    print("=" * 50)
                    print()
                    print("📋 Copy this into your .env file:")
                    print(f"   TIKTOK_REVIEW_CHAT={chat_id}")
                    print()
                    print("Then run: python tiktok/test_tiktok.py")
                    return
        except TelegramError as e:
            print(f"Error: {e}")
            break
        await asyncio.sleep(1)
        remaining = 30 - i - 1
        if remaining > 0 and remaining % 5 == 0:
            print(f"  Still waiting... ({remaining}s left)")

    print("⏰ Timeout — no message received.")
    print(f"Make sure you send a message to @{me.username} in Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
