"""sRGB <-> OKLCH conversion and the accent ramp .env's ACCENT_COLOR drives."""

from __future__ import annotations

import math
import re

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")

Oklch = tuple[float, float, float]
Rgb = tuple[float, float, float]

# Ramp stops, lightest to darkest. The lightness values are read off the reference Industry steel
# palette so that ACCENT_COLOR=#5980a6 lands close to the hand-picked hexes it replaces.
RAMP_STOPS: tuple[tuple[int, float, float], ...] = (
    # (stop, OKLCH lightness, chroma multiplier)
    (100, 0.970, 0.35),
    (200, 0.910, 0.50),
    (300, 0.850, 0.65),
    (400, 0.750, 0.80),
    (500, 0.650, 0.95),
    (600, 0.570, 1.00),
    (700, 0.450, 1.00),
    (800, 0.340, 0.85),
    (900, 0.250, 0.70),
)


def parse_hex(value: str) -> Rgb:
    match = HEX_RE.match(value.strip())
    if not match:
        raise ValueError(f"ACCENT_COLOR must be a 6-digit hex colour, got {value!r}")
    digits = match.group(1)
    channels = tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return channels[0], channels[1], channels[2]


def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def srgb_to_oklch(rgb: Rgb) -> Oklch:
    """(r, g, b) in 0..1 to (L, C, H) with L in 0..1, H in degrees. Björn Ottosson's OKLab."""
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l_, m_, s_))
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_lab = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    chroma = math.hypot(a, b_lab)
    hue = math.degrees(math.atan2(b_lab, a)) % 360
    return lightness, chroma, hue


def accent_ramp(hex_colour: str) -> dict[int, Oklch]:
    """The 100..900 ramp for one accent hex, as OKLCH triples.

    Hue is held constant so every stop reads as the same colour; only lightness and chroma move.
    """
    _, chroma, hue = srgb_to_oklch(parse_hex(hex_colour))
    return {
        stop: (lightness, round(chroma * multiplier, 4), round(hue, 2)) for stop, lightness, multiplier in RAMP_STOPS
    }


def oklch_css(triple: Oklch, alpha: float | None = None) -> str:
    lightness, chroma, hue = triple
    body = f"{lightness:.3f} {chroma:.4f} {hue:.2f}"
    return f"oklch({body} / {alpha})" if alpha is not None else f"oklch({body})"
