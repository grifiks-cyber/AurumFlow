import re
from typing import Optional, Dict, List, Tuple

NOISE_PATTERNS = [
    r"\+\d+\s*pips?",
    r"resumen\s+del\s+d[íi]a",
    r"movemos?\s+sl",
    r"asegurad",
    r"seguimos?\s+en\s+rango",
    r"ya\s+hemos?\s+llegado",
    r"objetivo\s+alcanzado",
    r"break\s*even",
    # NOTE: "cerramos rango" / "cerrad" removed from noise —
    # they are now handled by extract_close_signal() instead
]
_NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

# ── Close / manual exit detection ────────────────────────────────────────────
_CLOSE_KEYWORDS = [
    r"cerrad",           # cerrad posiciones, cerrad todo
    r"cerramos?\s+rango",
    r"cerramos?\s+trade",
    r"cerramos?\s+operaci",
    r"salimos",
    r"salid",
    r"exit\s+now",
    r"close\s+trade",
    r"close\s+all",
    r"manual\s+close",
    r"range\s+closed",
    r"closed\s+manually",
    r"cerramos?\s+manual",
]
_CLOSE_RE = re.compile("|".join(_CLOSE_KEYWORDS), re.IGNORECASE)


def extract_close_signal(text: str) -> bool:
    """
    Returns True if the message indicates TrueTrading is closing
    the active trade or range manually (before TP/SL).
    """
    if not text:
        return False
    return bool(_CLOSE_RE.search(text))


def is_noise(text: str) -> bool:
    if not text:
        return True
    return bool(_NOISE_RE.search(text))


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\n", " ").split())


def extract_signal(text: str) -> Optional[Dict]:
    if not text:
        return None
    clean = normalize_text(text)

    # ── Signal patterns checked FIRST — before noise filter ──────────────────
    # TrueTrading often includes "+20 pips" or "asegurar" context in the same
    # message as the actual BUY/SELL. Checking noise first kills valid signals.
    # Rule: if a BUY/SELL pattern matches anywhere → it's a signal, full stop.
    # All known TrueTrading SENALES formats:
    patterns = [
        # "Buy 4711 XAUUSD" / "Sell 4730 XAUUSD"
        r"\b(Buy|Sell)\s+(\d{3,5}(?:[.,]\d+)?)\s+XAUUSD\b",
        # "BUY XAUUSD 4711" / "SELL XAUUSD 4730"
        r"\b(BUY|SELL)\s+XAUUSD\s+(\d{3,5}(?:[.,]\d+)?)\b",
        # "XAUUSD BUY 4711" / "XAUUSD SELL 4730"
        r"\bXAUUSD\s+(BUY|SELL)\s+(\d{3,5}(?:[.,]\d+)?)\b",
        # "Buy XAUUSD @ 4711" / "Sell XAUUSD @ 4730"
        r"\b(Buy|Sell)\s+XAUUSD\s+@?\s*(\d{3,5}(?:[.,]\d+)?)\b",
        # "Buy zona 4711" / "Sell zona 4730" (zone entry)
        r"\b(Buy|Sell)\s+zona\s+(\d{3,5}(?:[.,]\d+)?)\b",
        # "Compra 4711 XAUUSD" / "Venta 4730 XAUUSD" (Spanish)
        r"\b(Compra|Venta)\s+(\d{3,5}(?:[.,]\d+)?)\s+XAUUSD\b",
        # "Compras en 4711" / "Ventas en 4730"
        r"\b(Compras?|Ventas?)\s+en\s+(\d{3,5}(?:[.,]\d+)?)\b",
    ]

    _SIDE_MAP = {
        "BUY": "BUY", "SELL": "SELL",
        "BUY": "BUY", "SELL": "SELL",
        "COMPRA": "BUY", "COMPRAS": "BUY",
        "VENTA": "SELL", "VENTAS": "SELL",
    }

    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            raw_side = match.group(1).upper()
            side = _SIDE_MAP.get(raw_side, raw_side)
            if side not in ("BUY", "SELL"):
                continue
            price = match.group(2).replace(",", ".")
            return {"type": side, "price": float(price), "raw_text": text}

    # No signal pattern found — now apply noise filter for stat tracking
    return None


def is_pure_noise(text: str) -> bool:
    """True only if the message has NO signal pattern and matches a noise pattern."""
    if extract_signal(text):
        return False
    return is_noise(text)


def extract_levels(text: str) -> List[float]:
    clean = normalize_text(text)
    matches = re.findall(r"\b\d{4,5}(?:[.,]\d+)?\b", clean)
    levels = []
    for m in matches:
        value = m.replace(",", ".")
        try:
            num = float(value)
            if 1900 <= num <= 2100:
                continue
            if 1000 <= num <= 10000:
                levels.append(num)
        except ValueError:
            continue
    return levels


def extract_bias(text: str) -> Optional[str]:
    clean = normalize_text(text).lower()
    if extract_signal(text):
        return None
    if any(w in clean for w in ["bajista", "bearish", "ventas", "sesgo bajista"]):
        return "BEARISH"
    if any(w in clean for w in ["alcista", "bullish", "compras", "sesgo alcista"]):
        return "BULLISH"
    if any(w in clean for w in ["rango", "lateral", "range"]):
        return "RANGE"
    return None


# ── Analysis zone parser ──────────────────────────────────────────────────────

_ZONE_PAIR_RE = re.compile(
    r"(\d{3,5}(?:[.,]\d+)?)\s*/\s*(\d{3,5}(?:[.,]\d+)?)"
)

def extract_analysis_zones(text: str) -> Dict[str, List[Tuple[float, float]]]:
    """
    Parses TrueTrading ANALISIS format:

      Posibles precios de venta (recomendados)
      4721 / 4724
      4747 / 4750
      ...
      Posibles precios de retrocesos (muy probables y funcionales hoy)
      4707 / 4704
      ...

    Returns:
      {
        "SELL": [(4721.0, 4724.0), (4747.0, 4750.0), ...],
        "BUY":  [(4704.0, 4707.0), ...]
      }
    Only populated if the relevant section is found; empty list otherwise.
    """
    if not text:
        return {"SELL": [], "BUY": []}

    lower = text.lower()
    has_sell = "posibles precios de venta" in lower
    has_buy  = any(kw in lower for kw in [
        "posibles precios de retrocesos",
        "posibles precios de compra",
        "retrocesos",
    ])

    if not has_sell and not has_buy:
        return {"SELL": [], "BUY": []}

    result: Dict[str, List[Tuple[float, float]]] = {"SELL": [], "BUY": []}
    current_type: Optional[str] = None

    for line in text.splitlines():
        line_lower = line.lower().strip()

        # Section headers
        if "posibles precios de venta" in line_lower:
            current_type = "SELL"
            continue
        if any(kw in line_lower for kw in [
            "posibles precios de retrocesos",
            "posibles precios de compra",
        ]):
            current_type = "BUY"
            continue

        # A new header-like line resets section if we don't know the type
        if current_type is None:
            continue

        # Parse zone pair
        m = _ZONE_PAIR_RE.search(line)
        if m:
            p1 = float(m.group(1).replace(",", "."))
            p2 = float(m.group(2).replace(",", "."))
            # Basic sanity: gold price range
            if 500 <= p1 <= 15000 and 500 <= p2 <= 15000:
                low  = min(p1, p2)
                high = max(p1, p2)
                result[current_type].append((low, high))

    return result
