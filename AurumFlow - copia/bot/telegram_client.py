import logging
from telethon import TelegramClient
from telethon.errors import SessionRevokedError, AuthKeyUnregisteredError
from config.settings import API_ID, API_HASH, SESSION_NAME

logger = logging.getLogger(__name__)


def build_client() -> TelegramClient:
    return TelegramClient(SESSION_NAME, API_ID, API_HASH)


async def get_recent_messages(client: TelegramClient, channel_id: int, limit: int = 20):
    try:
        entity = await client.get_entity(channel_id)
        messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            if msg.text:
                messages.append(msg)
        return messages
    except (SessionRevokedError, AuthKeyUnregisteredError):
        logger.critical("Session revoked — delete session.session and re-authenticate.")
        raise
    except Exception as e:
        logger.error(f"Error reading channel {channel_id}: {e}")
        return []
