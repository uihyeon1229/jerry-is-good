"""D4 — JSONL append-only 체크포인트.

사용 예:
    ckpt = Checkpoint(path)
    for row in rows:
        if ckpt.has(row['_row_id']):
            continue
        processed = process(row)
        ckpt.append(processed, row_id=row['_row_id'])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class Checkpoint:
    def __init__(self, path: Path, *, id_field: str = "_row_id") -> None:
        self.path = Path(path)
        self.id_field = id_field
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[str] = self._load_existing()

    def _load_existing(self) -> set[str]:
        if not self.path.exists():
            return set()
        done: set[str] = set()
        with self.path.open("r", encoding="utf-8") as fp:
            for line in fp:
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                    rid = row.get(self.id_field)
                    if rid is not None:
                        done.add(str(rid))
                except Exception:
                    continue
        return done

    @property
    def done_count(self) -> int:
        return len(self._done)

    def has(self, row_id) -> bool:
        if row_id is None:
            return False
        return str(row_id) in self._done

    def append(self, row: dict, *, row_id=None) -> None:
        rid = row_id if row_id is not None else row.get(self.id_field)
        if rid is None:
            raise ValueError(
                f"Checkpoint.append requires row_id or row[{self.id_field!r}]"
            )
        rid_str = str(rid)
        if rid_str in self._done:
            return
        row_out = {**row, self.id_field: rid}
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row_out, ensure_ascii=False, default=str) + "\n")
        self._done.add(rid_str)

    def filter_pending(self, rows: Iterable[dict]) -> list[dict]:
        """이미 처리된 행을 제외."""
        return [r for r in rows if not self.has(r.get(self.id_field))]
