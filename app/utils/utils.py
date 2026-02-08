"""General helper utilities."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json
import os

def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists and return it as a Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_text(path: str | Path) -> str:
    """Read a text file (utf-8) from disk."""
    return Path(path).read_text(encoding="utf-8")

def write_text(path: str | Path, text: str) -> None:
    """Write a text file (utf-8) to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def read_json(path: str | Path) -> Any:
    """Read JSON from disk."""
    return json.loads(read_text(path))

def write_json(path: str | Path, obj: Any) -> None:
    """Write JSON to disk (pretty)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Atomically write bytes to disk to avoid partial files."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, p)
