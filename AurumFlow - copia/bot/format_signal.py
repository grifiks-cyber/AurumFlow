from typing import Optional, Dict, List, Tuple
from config.settings import VT_MARKETS_LINK, SL_BUFFER_PIPS, TP1_PIPS, TP2_PIPS


def _validate(side, entry, sl, tp1, tp2):
    if side == "SELL":
        return sl > entry > tp1 > tp2
    return sl < entry < tp1 < tp2


def _compute(signal: dict, levels: list) -> Tuple:
    side  = signal["type"]
    entry = signal["price"]

    if levels and len(levels) >= 2:
        zone_low  = min(levels[:2])
        zone_high = max(levels[:2])
    else:
        zone_low  = entry
        zone_high = entry + 3 if side == "SELL" else entry - 3

    sl  = zone_high + SL_BUFFER_PIPS if side == "SELL" else zone_low - SL_BUFFER_PIPS
    tp1 = entry - TP1_PIPS           if side == "SELL" else entry + TP1_PIPS
    tp2 = entry - TP2_PIPS           if side == "SELL" else entry + TP2_PIPS

    return zone_low, zone_high, sl, tp1, tp2


def build_trade_message(
    signal: Optional[Dict],
    levels: Optional[List[float]],
    bias: Optional[str],
    entry_warning: bool = False,
) -> Optional[str]:
    """English version — published to main channel."""
    if not signal:
        return None

    side  = signal["type"]
    zone_low, zone_high, sl, tp1, tp2 = _compute(signal, levels or [])

    if not _validate(side, signal["price"], sl, tp1, tp2):
        return None

    # Context line
    if bias == "BEARISH":
        context = "Bearish structure confirmed — resistance reaction"
    elif bias == "BULLISH":
        context = "Bullish structure confirmed — support reaction"
    else:
        context = "Price reacting at key level"

    # Risk management context
    if side == "SELL":
        mgmt_context = "Bearish momentum active. Look to close partial at TP1."
    else:
        mgmt_context = "Bullish structure intact. Protect position at TP1."

    emoji = "🔴" if side == "SELL" else "🟢"

    warning = "\n⚠️ *Entry zone already advanced — higher risk*\n" if entry_warning else ""

    return (
        f"{emoji} *{side} XAUUSD — Aurum Flow Signal*\n"
        f"{warning}\n"
        f"📍 Entry Zone: `{zone_low:.0f} – {zone_high:.0f}`\n"
        f"🛑 Stop Loss: `{sl:.0f}`\n\n"
        f"🎯 *Take Profit Targets:*\n"
        f"  • TP1: `{tp1:.0f}`\n"
        f"  • TP2: `{tp2:.0f}`\n\n"
        f"🧠 *Context:* _{context}_\n\n"
        f"📊 *Risk Management:*\n"
        f"  • Close partial at TP1\n"
        f"  • Move SL to break-even after TP1\n"
        f"  • _{mgmt_context}_\n\n"
        f"🔥 Free signals: @AurumFlowXau\n"
        f"Broker: [VT Markets]({VT_MARKETS_LINK})"
    )


def build_trade_message_es(
    signal: Optional[Dict],
    levels: Optional[List[float]],
    bias: Optional[str],
    entry_warning: bool = False,
) -> Optional[str]:
    """Spanish version — published to secondary ES channel."""
    if not signal:
        return None

    side  = signal["type"]
    zone_low, zone_high, sl, tp1, tp2 = _compute(signal, levels or [])

    if not _validate(side, signal["price"], sl, tp1, tp2):
        return None

    # Context
    if bias == "BEARISH":
        context = "Estructura bajista confirmada — reacción en resistencia"
    elif bias == "BULLISH":
        context = "Estructura alcista confirmada — reacción en soporte"
    else:
        context = "Precio reaccionando en nivel clave"

    # Risk management
    if side == "SELL":
        mgmt_context = "Momento bajista activo. Cerrar parcial en TP1."
    else:
        mgmt_context = "Estructura alcista intacta. Proteger posición en TP1."

    lado_es = "VENTA" if side == "SELL" else "COMPRA"
    emoji   = "🔴" if side == "SELL" else "🟢"

    warning = "\n⚠️ *Zona de entrada ya avanzada — mayor riesgo*\n" if entry_warning else ""

    return (
        f"{emoji} *{lado_es} XAUUSD — Señal Aurum Flow*\n"
        f"{warning}\n"
        f"📍 Zona de entrada: `{zone_low:.0f} – {zone_high:.0f}`\n"
        f"🛑 Stop Loss: `{sl:.0f}`\n\n"
        f"🎯 *Objetivos:*\n"
        f"  • TP1: `{tp1:.0f}`\n"
        f"  • TP2: `{tp2:.0f}`\n\n"
        f"🧠 *Contexto:* _{context}_\n\n"
        f"📊 *Gestión:*\n"
        f"  • Cerrar parcial en TP1\n"
        f"  • Mover SL a break even tras TP1\n"
        f"  • _{mgmt_context}_\n\n"
        f"❌ Error típico: no asegurar → reversión → pérdida\n\n"
        f"🔥 Señales gratis: @AurumFlowXau\n"
        f"Broker: [VT Markets]({VT_MARKETS_LINK})"
    )
