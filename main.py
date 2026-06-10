import asyncio
import logging
import logging.handlers
import os
import sys

from bot.live_mirror import start_live_mirror
from bot.telegram_client import build_client
from data.state import init_db

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            "logs/aurumflow.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("aurumflow.main")


async def main():
    init_db()
    logger.info("=" * 50)
    logger.info("  Aurum Flow — TrueTrading Live Mirror")
    logger.info("  Mode          : instant Telethon NewMessage mirror")
    logger.info("  Log file      : logs/aurumflow.log")
    logger.info("=" * 50)

    client = build_client()
    await client.start()
    logger.info("Telegram session active.")

    try:
        await start_live_mirror(client)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested by user.")
    finally:
        await client.disconnect()
        logger.info("Aurum Flow stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
