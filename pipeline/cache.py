"""간단 디스크 캐시 (hash(text) → JSON). L2 verify_citations 재호출 방지용."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .settings import settings


def _cache_dir() -> Path:
    d = settings.cache_dir / "validators"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def get(tag: str, text: str) -> dict | None:
    path = _cache_dir() / f"{tag}_{_key(text)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def put(tag: str, text: str, value: dict) -> None:
    path = _cache_dir() / f"{tag}_{_key(text)}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
