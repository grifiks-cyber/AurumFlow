"""
TikTok Video Generator V2 — Aurum Flow
Premium institutional-style 9:16 MP4 videos.

Templates:
  - SIGNAL   : entry + SL/TP + bias + context
  - RESULT   : TP hit + pips celebration
  - NARRATIVE: smart money / bias narrative

Stack: Pillow + imageio-ffmpeg
"""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30

# ── Brand palette ─────────────────────────────────────────────────────────────
GOLD        = (212, 175, 55)
GOLD_DIM    = (140, 115, 35)
WHITE       = (255, 255, 255)
OFF_WHITE   = (220, 220, 220)
BLACK       = (8, 8, 8)
DARK        = (14, 14, 14)
CARD        = (20, 20, 20)
SELL_RED    = (220, 60, 50)
SELL_DIM    = (140, 35, 28)
BUY_GREEN   = (40, 200, 100)
BUY_DIM     = (24, 120, 60)
GREY        = (70, 70, 70)
LIGHT_GREY  = (130, 130, 130)


# ── Font loader ───────────────────────────────────────────────────────────────
_font_cache = {}

def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    from PIL import ImageFont
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/calibrib.ttf",
         "C:/Windows/Fonts/verdanab.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf",
         "C:/Windows/Fonts/verdana.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _font_cache[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ── Drawing helpers ───────────────────────────────────────────────────────────
def _text_w(draw, text: str, font) -> int:
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * (font.size // 2 if hasattr(font, 'size') else 10)


def _centered_text(draw, y: int, text: str, size: int,
                   color: tuple, bold: bool = False):
    f = _font(size, bold)
    w = _text_w(draw, text, f)
    draw.text(((W - w) / 2, y), text, font=f, fill=color)
    return size + 8


def _draw_hline(draw, y: int, color: tuple, width: int = 1,
                margin: int = 60):
    draw.rectangle([(margin, y), (W - margin, y + width)], fill=color)


def _draw_card(draw, y_top: int, y_bot: int, color: tuple = CARD,
               border: tuple = None):
    draw.rectangle([(48, y_top), (W - 48, y_bot)], fill=color)
    if border:
        draw.rectangle([(48, y_top), (51, y_bot)], fill=border)


# ── Base canvas ───────────────────────────────────────────────────────────────
def _base_canvas(accent: tuple = GOLD) -> "Image":
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)

    # Subtle vignette gradient
    for y in range(H):
        v = int(6 * (1 - abs(y / H - 0.5) * 2))
        draw.line([(0, y), (W, y)], fill=(v, v, v))

    # Top accent bar
    draw.rectangle([(0, 0), (W, 5)], fill=accent)

    # Bottom accent bar
    draw.rectangle([(0, H - 5), (W, H)], fill=accent)

    # Logo area top-right
    f_logo  = _font(22, bold=True)
    f_sub   = _font(16)
    logo_x  = W - 48
    draw.text((logo_x, 28), "AURUM", font=f_logo, fill=accent, anchor="ra")
    draw.text((logo_x, 52), "FLOW", font=f_sub,  fill=LIGHT_GREY, anchor="ra")

    # Thin vertical left accent
    draw.rectangle([(40, 80), (42, H - 80)], fill=(*accent[:3], 30) if len(accent) == 3 else GOLD_DIM)

    return img, draw


# ── SIGNAL template V2 ────────────────────────────────────────────────────────
def _signal_frames_v2(direction: str, entry: float, sl: float,
                       tp1: float, tp2: float, bias: str,
                       context: str = "") -> list:

    accent     = SELL_RED  if direction == "SELL" else BUY_GREEN
    accent_dim = SELL_DIM  if direction == "SELL" else BUY_DIM
    dir_emoji  = "▼" if direction == "SELL" else "▲"
    frames     = []

    # ── Scene 1: Alert flash (20 frames / 0.7s) ───────────────────────────────
    img, draw = _base_canvas(accent)
    _centered_text(draw, 380, "SIGNAL ALERT", 38, LIGHT_GREY)
    _centered_text(draw, 440, "XAUUSD", 52, WHITE, bold=True)
    _draw_hline(draw, 520, GREY)
    _centered_text(draw, 560, f"{dir_emoji}  {direction}", 110, accent, bold=True)
    frames.extend([img] * 20)

    # ── Scene 2: Entry (55 frames / ~1.8s) ───────────────────────────────────
    img, draw = _base_canvas(accent)
    _centered_text(draw, 300, "XAUUSD", 40, LIGHT_GREY)
    _centered_text(draw, 360, direction, 130, accent, bold=True)

    # Entry card
    _draw_card(draw, 530, 650, CARD, accent)
    _centered_text(draw, 548, "ENTRY ZONE", 24, LIGHT_GREY)
    _centered_text(draw, 582, f"{entry:.0f}", 72, WHITE, bold=True)

    frames.extend([img] * 55)

    # ── Scene 3: Levels (80 frames / ~2.7s) ──────────────────────────────────
    img, draw = _base_canvas(accent)

    _centered_text(draw, 220, direction, 72, accent, bold=True)
    _centered_text(draw, 308, "XAUUSD", 36, LIGHT_GREY)
    _draw_hline(draw, 370, GREY)

    # Entry
    _draw_card(draw, 400, 510, CARD)
    _centered_text(draw, 416, "ENTRY", 26, LIGHT_GREY)
    _centered_text(draw, 452, f"{entry:.0f}", 56, WHITE, bold=True)

    # SL / TP side by side
    mid = W // 2
    # SL card (left)
    draw.rectangle([(48, 540), (mid - 12, 650)], fill=CARD)
    draw.rectangle([(48, 540), (51, 650)], fill=SELL_RED)
    f26 = _font(26)
    f48 = _font(48, bold=True)
    draw.text((mid // 2, 556), "STOP LOSS", font=f26, fill=LIGHT_GREY, anchor="mm")
    draw.text((mid // 2, 608), f"{sl:.0f}", font=f48, fill=SELL_RED, anchor="mm")

    # TP card (right)
    draw.rectangle([(mid + 12, 540), (W - 48, 650)], fill=CARD)
    draw.rectangle([(mid + 12, 540), (mid + 15, 650)], fill=BUY_GREEN)
    draw.text(((mid + W) // 2, 556), "TP1", font=f26, fill=LIGHT_GREY, anchor="mm")
    draw.text(((mid + W) // 2, 608), f"{tp1:.0f}", font=f48, fill=BUY_GREEN, anchor="mm")

    # TP2
    _draw_card(draw, 670, 760, CARD)
    _centered_text(draw, 686, "TP2", 26, LIGHT_GREY)
    _centered_text(draw, 718, f"{tp2:.0f}", 48, BUY_GREEN, bold=True)

    # Bias
    _draw_hline(draw, 790, GREY)
    bias_color = SELL_RED if bias == "BEARISH" else BUY_GREEN if bias == "BULLISH" else LIGHT_GREY
    _centered_text(draw, 810, f"BIAS  ·  {bias}", 30, bias_color, bold=True)

    frames.extend([img] * 80)

    # ── Scene 4: Context + CTA (120 frames / 4s) ─────────────────────────────
    img, draw = _base_canvas(accent)

    y = 280
    # Context lines
    ctx_lines = [l.strip() for l in context.split("\n") if l.strip()][:4]
    if not ctx_lines:
        ctx_lines = [
            "Selling pressure remains active." if direction == "SELL"
            else "Buying pressure remains active."
        ]
    for line in ctx_lines:
        _centered_text(draw, y, line, 36, OFF_WHITE)
        y += 52

    _draw_hline(draw, y + 20, GOLD_DIM)
    y += 50

    # Bias pill
    _draw_card(draw, y, y + 70, CARD, accent_dim)
    _centered_text(draw, y + 16, f"Market Bias: {bias}", 32, accent, bold=True)
    y += 100

    # CTA
    _draw_hline(draw, H - 200, GREY)
    _centered_text(draw, H - 170, "Free signals  ·  Link in bio", 30, LIGHT_GREY)
    _centered_text(draw, H - 122, "@aurumflowsignals", 28, GOLD, bold=True)

    frames.extend([img] * 120)

    return frames


# ── RESULT template V2 ────────────────────────────────────────────────────────
def _result_frames_v2(direction: str, pips: int, context: str = "") -> list:
    frames = []
    img, draw = _base_canvas(BUY_GREEN)

    _centered_text(draw, 300, "TARGET HIT", 52, BUY_GREEN, bold=True)
    _draw_hline(draw, 380, GOLD_DIM)
    _centered_text(draw, 410, f"+{pips}", 160, WHITE, bold=True)
    _centered_text(draw, 582, "PIPS", 52, GOLD, bold=True)
    _draw_hline(draw, 660, GREY)
    _centered_text(draw, 690, f"XAUUSD {direction}", 40, LIGHT_GREY)

    ctx = context.split("\n")[0].strip() if context else "Another clean setup executed."
    _centered_text(draw, 780, ctx, 32, OFF_WHITE)

    _centered_text(draw, H - 160, "Free signals  ·  Link in bio", 30, LIGHT_GREY)
    _centered_text(draw, H - 112, "@aurumflowsignals", 28, GOLD, bold=True)

    frames.extend([img] * 200)
    return frames


# ── NARRATIVE template V2 ─────────────────────────────────────────────────────
def _narrative_frames_v2(direction: str, bias: str, context: str = "") -> list:
    accent = SELL_RED if direction == "SELL" else BUY_GREEN
    frames = []
    lines  = [l.strip() for l in context.split("\n") if l.strip()][:5]

    if not lines:
        lines = [
            "Smart money was active.", f"Structure: {bias}",
            f"XAUUSD aligned {direction}."
        ]

    # Scene 1
    img, draw = _base_canvas(accent)
    y = 380
    for line in lines[:3]:
        _centered_text(draw, y, line, 46, WHITE, bold=True)
        y += 72
    frames.extend([img] * 110)

    # Scene 2
    img, draw = _base_canvas(accent)
    _centered_text(draw, 360, "XAUUSD", 48, LIGHT_GREY)
    _centered_text(draw, 430, direction, 120, accent, bold=True)
    bias_color = SELL_RED if bias == "BEARISH" else BUY_GREEN
    _centered_text(draw, 570, bias, 44, bias_color, bold=True)
    _draw_hline(draw, 640, GREY)
    _centered_text(draw, 670, "Were you watching?", 34, OFF_WHITE)
    _centered_text(draw, H - 160, "Free signals  ·  Link in bio", 30, LIGHT_GREY)
    _centered_text(draw, H - 112, "@aurumflowsignals", 28, GOLD, bold=True)
    frames.extend([img] * 140)

    return frames


# ── Video writer ──────────────────────────────────────────────────────────────
def _write_video(frames: list, path: str) -> bool:
    try:
        import imageio
        import numpy as np
        writer = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8,
                                    macro_block_size=None)
        for f in frames:
            writer.append_data(np.array(f))
        writer.close()
        return True
    except Exception as e:
        logger.error(f"Video write error: {e}")
        return False


# ── Public async API ──────────────────────────────────────────────────────────
async def generate_signal_video(direction: str, entry: float, sl: float,
                                 tp1: float, tp2: float, bias: str,
                                 copy_text: str = "",
                                 context: str = "") -> Optional[str]:
    """
    Production: generate a V2 signal video.
    copy_text = TikTok caption (for metadata/reference)
    context   = AI-rewritten context lines shown in Scene 4
    """
    try:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(OUTPUT_DIR / f"signal_{direction}_{ts}.mp4")

        ctx = context or copy_text

        def _gen():
            frames = _signal_frames_v2(direction, entry, sl, tp1, tp2, bias, ctx)
            return _write_video(frames, path)

        ok = await asyncio.get_event_loop().run_in_executor(None, _gen)
        if ok:
            logger.info(f"Signal video generated: {path}")
            return path
        return None
    except Exception as e:
        logger.error(f"generate_signal_video error: {e}")
        return None


async def generate_result_video(direction: str, pips: int,
                                 copy_text: str = "") -> Optional[str]:
    try:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(OUTPUT_DIR / f"result_{direction}_{pips}pips_{ts}.mp4")

        def _gen():
            frames = _result_frames_v2(direction, pips, copy_text)
            return _write_video(frames, path)

        ok = await asyncio.get_event_loop().run_in_executor(None, _gen)
        return path if ok else None
    except Exception as e:
        logger.error(f"generate_result_video error: {e}")
        return None


async def generate_narrative_video(direction: str, bias: str,
                                    copy_text: str = "") -> Optional[str]:
    try:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(OUTPUT_DIR / f"narrative_{direction}_{ts}.mp4")

        def _gen():
            frames = _narrative_frames_v2(direction, bias, copy_text)
            return _write_video(frames, path)

        ok = await asyncio.get_event_loop().run_in_executor(None, _gen)
        return path if ok else None
    except Exception as e:
        logger.error(f"generate_narrative_video error: {e}")
        return None
