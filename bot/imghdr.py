# imghdr.py — Polyfill for Python 3.13+ (imghdr was removed from stdlib)
"""Polyfill to fix tweepy import on Python 3.13/3.14+."""
from pathlib import Path

def what(file, h=None) -> str | None:
    if file:
        file_path = Path(file)
        if file_path.exists():
            with open(file_path, "rb") as f:
                h = f.read(32)
    if not h:
        return None
    # Simple header checks for common formats
    if h.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if h.startswith(b"GIF87a") or h.startswith(b"GIF89a"):
        return "gif"
    if h.startswith(b"RIFF") and h[8:12] == b"WEBP":
        return "webp"
    return None
