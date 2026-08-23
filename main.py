"""HexArena entry point: opens the game in a native window via pywebview."""

from __future__ import annotations

import os
import sys

import webview

from engine.api import Api


def _ui_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui", *parts)


def main() -> None:
    api = Api()
    window = webview.create_window(
        "HexArena",
        _ui_path("index.html"),
        js_api=api,
        width=1180,
        height=880,
        min_size=(860, 680),
        background_color="#0a0a0f",
    )
    api.bind(window)
    webview.start()


if __name__ == "__main__":
    main()
