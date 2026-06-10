import asyncio
import logging
import logging.handlers
import os
import sys

from config.settings import LOOP_INTERVAL
from bot.telegram_client import build_client
from bot.full_pipeline import run_pipeline
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
MAX_ERRORS = 10


async def main():
    init_db()
    logger.info("=" * 50)
    logger.info("  Aurum Flow — XAUUSD Signal Bot")
    logger.info(f"  Loop interval : {LOOP_INTERVAL}s")
    logger.info(f"  Log file      : logs/aurumflow.log")
    logger.info("=" * 50)

    client = build_client()
    await client.start()
    logger.info("Telegram session active.")

    consecutive_errors = 0
    cycle = 0

    while True:
        cycle += 1
        try:
            await run_pipeline(client)
            consecutive_errors = 0

        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown requested by user.")
            break

        except Exception as e:
            consecutive_errors += 1
            logger.error(
                f"Unhandled error in cycle {cycle} "
                f"({consecutive_errors}/{MAX_ERRORS}): {e}",
                exc_info=True,
            )
            if consecutive_errors >= MAX_ERRORS:
                logger.critical(
                    f"Too many consecutive errors ({MAX_ERRORS}) — stopping."
                )
                sys.exit(1)

        logger.info(f"Sleeping {LOOP_INTERVAL}s...\n")
        await asyncio.sleep(LOOP_INTERVAL)

    await client.disconnect()
    logger.info("Aurum Flow stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
