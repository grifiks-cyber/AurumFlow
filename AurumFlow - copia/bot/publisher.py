import logging
import asyncio
from telegram import Bot
from telegram.error import RetryAfter, TelegramError
from config.settings import BOT_TOKEN, OUTPUT_CHANNEL, OUTPUT_CHANNEL_ES

logger = logging.getLogger(__name__)
_bot = Bot(token=BOT_TOKEN)


async def _send_to(chat_id: str, message: str, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            await _bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            logger.info(f"Published to {chat_id}")
            return True
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(f"Rate limited — waiting {wait}s (attempt {attempt}/{retries})")
            await asyncio.sleep(wait)
        except TelegramError as e:
            logger.error(f"Telegram error attempt {attempt} → {chat_id}: {e}")
            await asyncio.sleep(2)
    logger.error(f"Failed to publish to {chat_id} after all retries.")
    return False


async def publish_signal(message: str, message_es: str = None, retries: int = 3) -> bool:
    """
    Publish to main English channel.
    If message_es provided AND CHANNEL_ES configured, also publish Spanish version.
    """
    sent = await _send_to(OUTPUT_CHANNEL, message, retries)

    if sent and message_es and OUTPUT_CHANNEL_ES:
        await asyncio.sleep(1)  # slight delay to avoid flooding
        await _send_to(OUTPUT_CHANNEL_ES, message_es, retries)

    return sent
