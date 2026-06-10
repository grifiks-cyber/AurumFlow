import logging
from typing import Any

from telethon import events
from telethon.tl.custom.message import Message

from config.settings import OUTPUT_ANALYSIS_CHANNEL, OUTPUT_CHANNEL, SOURCE_CHANNELS

logger = logging.getLogger(__name__)


def _message_text(message: Message) -> str:
    """Return Telegram's original message text/caption without rewriting it."""
    return message.message or ""


async def _copy_message(client: Any, message: Message, destination: str, label: str) -> None:
    """Copy one Telegram message to the configured destination as-is."""
    text = _message_text(message)
    entities = message.entities or None

    if message.media:
        await client.send_file(
            destination,
            message.media,
            caption=text,
            formatting_entities=entities,
        )
        logger.info(
            "Copied %s media message %s to %s.",
            label,
            message.id,
            destination,
        )
        return

    await client.send_message(
        destination,
        text,
        formatting_entities=entities,
    )
    logger.info(
        "Copied %s text message %s to %s.",
        label,
        message.id,
        destination,
    )


async def start_live_mirror(client: Any) -> None:
    """Start instant mirroring from TrueTrading sources to AurumFlow channels."""
    signals_source = SOURCE_CHANNELS["SENALES"]
    analysis_source = SOURCE_CHANNELS["ANALISIS"]

    @client.on(events.NewMessage(chats=signals_source))
    async def mirror_signal(event: events.NewMessage.Event) -> None:
        try:
            await _copy_message(client, event.message, OUTPUT_CHANNEL, "signal")
        except Exception:
            logger.exception(
                "Failed to copy signal message %s to %s.",
                getattr(event.message, "id", "unknown"),
                OUTPUT_CHANNEL,
            )

    @client.on(events.NewMessage(chats=analysis_source))
    async def mirror_analysis(event: events.NewMessage.Event) -> None:
        try:
            await _copy_message(
                client,
                event.message,
                OUTPUT_ANALYSIS_CHANNEL,
                "analysis",
            )
        except Exception:
            logger.exception(
                "Failed to copy analysis message %s to %s.",
                getattr(event.message, "id", "unknown"),
                OUTPUT_ANALYSIS_CHANNEL,
            )

    logger.info(
        "Live mirror started: signals %s -> %s | analysis %s -> %s.",
        signals_source,
        OUTPUT_CHANNEL,
        analysis_source,
        OUTPUT_ANALYSIS_CHANNEL,
    )
    await client.run_until_disconnected()
