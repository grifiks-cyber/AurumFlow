"""
Result Video Generator — Aurum Flow
Generates announcement cards for TP1 / TP2 / SL / CLOSE events.

Short 5-second 9:16 MP4 with two scenes:
  Scene 1 (0–2.5s): Event flash (big result badge)
  Scene 2 (2.5–5s): Detail card (pips, levels, tagline)

Same brand palette and stack as video_generator.py (Pillow + imageio-ffmpeg).
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
FPS  = 30

# ── Brand palette (matches video_generator.py) ────────────────────────────────
GOLD       = (212, 175, 55)
GOLD_DIM   = (140, 115, 35)
WHITE      = (255, 255, 255)
OFF_WHITE  = (220, 220, 220)
BLACK      = (8, 8, 8)
DARK       = (14, 14, 14)
CARD       = (22, 22, 22)
SELL_RED   = (220, 60, 50)
BUY_GREEN  = (40, 200, 100)
GREY       = (70, 70, 70)
LIGHT_GREY = (130, 130, 130)
WARN_AMBER = (230, 160, 30)

# ── Event config ──────────────────────────────────────────────────────────────
EVENT_CONFIG = {
    "TP1": {
        "accent":   BUY_GREEN,
        "badge":    "✓ TP1 HIT",
        "tagline":  "First target reached",
        "symbol":   "+",
        "bg_tint":  (10, 30, 18),
    },
    "TP2": {
        "accent":   GOLD,
        "badge":    "★ FULL TARGET",
        "tagline":  "Smart money move",
        "symbol":   "+",
        "bg_tint":  (22, 18, 5),
    },
    "SL": {
        "accent":   SELL_RED,
        "badge":    "✕ STOP LOSS",
        "tagline":  "Risk managed. Next setup loading...",
        "symbol":   "−",
        "bg_tint":  (28, 8, 8),
    },
    "CLOSE": {
        "accent":   WARN_AMBER,
        "badge":    "⚠ MANUAL EXIT",
        "tagline":  "Position closed by source",
        "symbol":   "",
        "bg_tint":  (25, 20, 5),
    },
}


def _font(size: int, bold: bool = False):
    try:
        from PIL import ImageFont
        import sys
        # Try system fonts (Windows)
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for p in font_paths:
            if Path(p).exists():
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def _draw_centered(draw, text: str, y: int, font, color, width=W):
    try:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = len(text) * (font.size // 2) if hasattr(font, 'size') else len(text) * 10
    x = (width - tw) // 2
    draw.text((x, y), text, font=font, fill=color)


def _make_scene1(event: str, direction: str, pips: Optional[int]) -> "Image":
    """Big result badge on dark tinted background."""
    from PIL import Image, ImageDraw

    cfg     = EVENT_CONFIG.get(event, EVENT_CONFIG["CLOSE"])
    accent  = cfg["accent"]
    tint    = cfg["bg_tint"]
    badge   = cfg["badge"]
    symbol  = cfg["symbol"]

    img  = Image.new("RGB", (W, H), color=tint)
    draw = ImageDraw.Draw(img)

    # Subtle gradient lines (brand texture)
    for i in range(0, H, 60):
        alpha = 15
        draw.line([(0, i), (W, i)], fill=(*DARK, alpha), width=1)

    # Top bar — gold
    draw.rectangle([0, 0, W, 8], fill=GOLD)

    # AURUM FLOW header
    f_small = _font(38)
    _draw_centered(draw, "AURUM FLOW", 90, f_small, GOLD_DIM)

    # ── Event badge ──────────────────────────────────────────────────────────
    badge_y = 680
    # Badge pill background
    bw, bh = 700, 110
    bx = (W - bw) // 2
    draw.rounded_rectangle([bx, badge_y, bx + bw, badge_y + bh],
                           radius=55, fill=accent)
    f_badge = _font(58, bold=True)
    _draw_centered(draw, badge, badge_y + 22, f_badge, BLACK)

    # ── Pips number (big) ────────────────────────────────────────────────────
    if pips is not None and event != "CLOSE":
        pip_text = f"{symbol}{abs(pips)} PIPS"
        f_pips   = _font(148, bold=True)
        _draw_centered(draw, pip_text, 820, f_pips, WHITE)

    # ── Direction label ──────────────────────────────────────────────────────
    dir_color = BUY_GREEN if direction == "BUY" else SELL_RED
    f_dir = _font(52, bold=True)
    _draw_centered(draw, f"XAUUSD {direction}", 1030, f_dir, dir_color)

    # Bottom CTA
    f_cta = _font(36)
    _draw_centered(draw, "@aurumflowsignals", H - 110, f_cta, LIGHT_GREY)

    return img


def _make_scene2(event: str, direction: str, entry: float,
                 sl: float, tp1: float, tp2: float,
                 pips: Optional[int]) -> "Image":
    """Detail card with levels + tagline."""
    from PIL import Image, ImageDraw

    cfg    = EVENT_CONFIG.get(event, EVENT_CONFIG["CLOSE"])
    accent = cfg["accent"]
    tint   = cfg["bg_tint"]
    tagline = cfg["tagline"]

    img  = Image.new("RGB", (W, H), color=tint)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W, 8], fill=GOLD)

    # Header
    f_small = _font(38)
    _draw_centered(draw, "AURUM FLOW", 70, f_small, GOLD_DIM)

    # ── Result line ──────────────────────────────────────────────────────────
    result_y = 200
    if pips is not None and event != "CLOSE":
        symbol   = cfg["symbol"]
        pip_text = f"{symbol}{abs(pips)} pips"
        f_result = _font(88, bold=True)
        _draw_centered(draw, pip_text, result_y, f_result, accent)
    else:
        f_result = _font(72, bold=True)
        _draw_centered(draw, cfg["badge"], result_y, f_result, accent)

    # ── Levels card ──────────────────────────────────────────────────────────
    card_y = 420
    cx, cw, ch = 80, W - 160, 560
    draw.rounded_rectangle([cx, card_y, cx + cw, card_y + ch],
                           radius=24, fill=CARD)

    f_label = _font(38)
    f_value = _font(54, bold=True)
    row_h   = 100
    rows = [
        ("Direction",  f"XAUUSD {direction}", BUY_GREEN if direction == "BUY" else SELL_RED),
        ("Entry Zone", f"{entry:.0f}",         WHITE),
        ("Stop Loss",  f"{sl:.0f}",            SELL_RED),
        ("TP1",        f"{tp1:.0f}",           BUY_GREEN),
        ("TP2",        f"{tp2:.0f}",           GOLD),
    ]
    for i, (label, value, val_color) in enumerate(rows):
        ry = card_y + 28 + i * row_h
        draw.text((cx + 36, ry), label, font=f_label, fill=LIGHT_GREY)
        draw.text((cx + 36, ry + 40), value, font=f_value, fill=val_color)
        if i < len(rows) - 1:
            draw.line([(cx + 36, ry + row_h - 4), (cx + cw - 36, ry + row_h - 4)],
                      fill=GREY, width=1)

    # ── Tagline ──────────────────────────────────────────────────────────────
    f_tag = _font(44)
    _draw_centered(draw, tagline, 1080, f_tag, OFF_WHITE)

    # ── CTA ─────────────────────────────────────────────────────────────────
    f_cta = _font(36)
    _draw_centered(draw, "Signals → @AurumFlowXau", H - 160, f_cta, GOLD_DIM)
    _draw_centered(draw, "@aurumflowsignals", H - 110, f_cta, LIGHT_GREY)

    return img


async def generate_result_video(
    event: str,          # "TP1" | "TP2" | "SL" | "CLOSE"
    direction: str,      # "SELL" | "BUY"
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    pips: Optional[int] = None,
) -> Optional[str]:
    """
    Generate a 5-second result announcement video.
    Returns path to MP4 or None on failure.
    """
    try:
        import numpy as np
        import imageio

        logger.info(f"Result video: generating {event} {direction} ({pips} pips)...")

        scene1 = _make_scene1(event, direction, pips)
        scene2 = _make_scene2(event, direction, entry, sl, tp1, tp2, pips)

        frames = []

        # Scene 1: 2.5s = 75 frames
        arr1 = np.array(scene1)
        for _ in range(int(FPS * 2.5)):
            frames.append(arr1)

        # Crossfade: 0.3s = 9 frames
        arr2 = np.array(scene2)
        for i in range(9):
            alpha = i / 9
            blend = (arr1 * (1 - alpha) + arr2 * alpha).astype(np.uint8)
            frames.append(blend)

        # Scene 2: remaining ~2.2s
        for _ in range(int(FPS * 2.2)):
            frames.append(arr2)

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{event.lower()}_{direction.lower()}_{ts}.mp4"
        path = OUTPUT_DIR / name

        writer = imageio.get_writer(
            str(path), fps=FPS, codec="libx264",
            output_params=["-crf", "26", "-preset", "fast",
                           "-pix_fmt", "yuv420p"],
        )
        for frame in frames:
            writer.append_data(frame)
        writer.close()

        size_kb = path.stat().st_size // 1024
        logger.info(f"Result video saved: {path} ({size_kb}KB)")
        return str(path)

    except Exception as e:
        logger.error(f"Result video generation failed: {e}")
        return None
