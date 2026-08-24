"""Generates docs/preview.svg: a static mock-up of the board in the app's
actual dark theme, for the README. Not part of the app itself — there is no
way to screenshot the native pywebview window from here, so this reuses the
same hex geometry as ui/app.js to render a believable mid-game position.

Run with: python scripts/make_preview.py
"""

from __future__ import annotations

import math
import os

SIZE = 7
PAD = 26
R = 34  # hex radius, generous for a crisp README image

BG = "#0a0a0f"
SURFACE = "#111118"
BORDER = "#1e1e2e"
P1 = "#e84545"
P1_GLOW = "rgba(232,69,69,0.45)"
P1_WIN = "#ff7070"
P2 = "#4a9eff"
P2_GLOW = "rgba(74,158,255,0.45)"
EMPTY = "#1a1a28"
STROKE = "#2a2a40"

# 0 = empty, 1 = red (top<->bottom), 2 = blue (left<->right)
BOARD = [[0] * SIZE for _ in range(SIZE)]
WIN_PATH = [(r, 3) for r in range(SIZE)]
for r, c in WIN_PATH:
    BOARD[r][c] = 1
for r, c in [(2, 5), (4, 1)]:
    BOARD[r][c] = 1
for r, c in [(2, 1), (3, 1), (1, 5), (4, 5), (5, 1)]:
    BOARD[r][c] = 2

WIN_SET = set(WIN_PATH)


def hex_center(row: int, col: int) -> tuple[float, float]:
    hex_w = R * math.sqrt(3)
    cx = PAD + hex_w * col + (hex_w / 2) * row
    cy = PAD + 1.5 * R * row
    return cx, cy


def hex_corners(cx: float, cy: float, r: float) -> str:
    pts = []
    for i in range(6):
        a = math.radians(60 * i - 30)
        pts.append(f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}")
    return " ".join(pts)


def main() -> None:
    last_cx, last_cy = hex_center(SIZE - 1, SIZE - 1)
    board_w = last_cx + R + PAD
    board_h = last_cy + (R * math.sqrt(3)) / 2 + PAD
    margin = 30
    W = board_w + margin * 2
    H = board_h + margin * 2

    parts: list[str] = []
    parts.append(f'<svg viewBox="0 0 {W:.0f} {H:.0f}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, sans-serif">')
    parts.append(f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" rx="20" fill="{BG}"/>')
    parts.append(f'<rect x="8" y="8" width="{W-16:.0f}" height="{H-16:.0f}" rx="16" fill="{SURFACE}" stroke="{BORDER}"/>')

    ox, oy = margin, margin

    def edge_line(r1, c1, r2, c2, color):
        x1, y1 = hex_center(r1, c1)
        x2, y2 = hex_center(r2, c2)
        parts.append(
            f'<line x1="{x1+ox:.2f}" y1="{y1+oy:.2f}" x2="{x2+ox:.2f}" y2="{y2+oy:.2f}" '
            f'stroke="{color}" stroke-width="4" stroke-linecap="round" opacity="0.55"/>'
        )

    for c in range(SIZE - 1):
        edge_line(0, c, 0, c + 1, P1)
        edge_line(SIZE - 1, c, SIZE - 1, c + 1, P1)
    for r in range(SIZE - 1):
        edge_line(r, 0, r + 1, 0, P2)
        edge_line(r, SIZE - 1, r + 1, SIZE - 1, P2)

    for r in range(SIZE):
        for c in range(SIZE):
            cx, cy = hex_center(r, c)
            cx, cy = cx + ox, cy + oy
            val = BOARD[r][c]
            in_win = (r, c) in WIN_SET
            if val == 0:
                fill, glow = EMPTY, None
            elif val == 1:
                fill, glow = (P1_WIN if in_win else P1), P1_GLOW
            else:
                fill, glow = P2, P2_GLOW

            filt = ""
            if glow:
                filt = f' style="filter:drop-shadow(0 0 6px {glow})"'
            parts.append(f'<polygon points="{hex_corners(cx, cy, R - 2)}" fill="{fill}" stroke="{STROKE}" stroke-width="1.5"{filt}/>')

    parts.append("</svg>")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "preview.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
