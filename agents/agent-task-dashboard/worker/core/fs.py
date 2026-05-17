from __future__ import annotations

import hashlib
import os
import struct
import zlib
from pathlib import Path
from typing import Any

from .common import pretty_json, safe_text

def resolve_artifact_root(task: dict[str, Any]) -> Path:
    override = os.environ.get("AGENT_ARTIFACT_ROOT")
    if override:
        root = Path(override)
    else:
        root = Path.cwd() / "public" / "generated" / "worker"
    root.mkdir(parents=True, exist_ok=True)
    return root / safe_text(task.get("id"), "unknown-task")

def public_url_for(path: Path) -> str:
    public_root = Path(os.environ.get("AGENT_PUBLIC_ROOT", Path.cwd() / "public"))
    try:
        return "/" + path.relative_to(public_root).as_posix()
    except ValueError:
        return path.as_posix()

def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path

def write_json(path: Path, data: Any) -> Path:
    return write_text(path, pretty_json(data) + "\n")

def write_placeholder_png(path: Path, seed: str, size: tuple[int, int] | None = None) -> Path:
    width, height = size or (1024, 1024)
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    base = [digest[0], digest[1], digest[2]]
    accent = [digest[3], digest[4], digest[5]]
    stripe = [digest[6], digest[7], digest[8]]

    def pixel(x: int, y: int) -> bytes:
        t = (x / max(width - 1, 1) + y / max(height - 1, 1)) / 2
        r = int(base[0] * (1 - t) + accent[0] * t)
        g = int(base[1] * (1 - t) + accent[1] * t)
        b = int(base[2] * (1 - t) + accent[2] * t)
        band = ((x // 64) + (y // 64)) % 2
        if band == 0:
            r = min(255, int(r * 0.9 + stripe[0] * 0.1))
            g = min(255, int(g * 0.9 + stripe[1] * 0.1))
            b = min(255, int(b * 0.9 + stripe[2] * 0.1))
        return bytes((r, g, b, 255))

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png.extend(chunk(b"IEND", b""))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(png))
    return path
