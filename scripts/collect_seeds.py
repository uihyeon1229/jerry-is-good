"""법제처 Open API로 세목별 조문 시드 수집 → cache/seeds/*.jsonl 저장.

사용법:
    LAW_OC=didwjs12 python scripts/collect_seeds.py

법제처 API 스펙:
- lawSearch.do: 법령 목록 검색
- lawService.do: 특정 법령의 상세 조문

※ Korean Law MCP (chrisryugj/korean-law-mcp)의 백엔드도 동일 API.
  최종 verify_citations에서는 MCP를 쓰되, 시드 수집은 직접 호출이 빠름.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OC = os.getenv("LAW_OC", "").strip()
if not OC:
    print("ERROR: LAW_OC 환경변수를 설정하세요.", file=sys.stderr)
    sys.exit(1)

OUT_DIR = Path(os.getenv("PIPELINE_SEED_DIR", "./cache/seeds"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://www.law.go.kr/DRF"


# 세목 → 대상 법령 목록
TARGETS = {
    "income_tax": ["소득세법", "소득세법 시행령", "소득세법 시행규칙"],
    "corporate_tax": ["법인세법", "법인세법 시행령"],
    "vat": ["부가가치세법", "부가가치세법 시행령"],
    "inheritance_gift_tax": ["상속세 및 증여세법", "상속세 및 증여세법 시행령"],
}


def _get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "track-c-seed-collector/0.1"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_law(name: str) -> dict | None:
    params = {
        "OC": OC,
        "target": "law",
        "query": name,
        "type": "JSON",
        "display": 3,
    }
    url = f"{BASE}/lawSearch.do?{urlencode(params)}"
    data = _get(url)
    laws = data.get("LawSearch", {}).get("law") or []
    for law in laws:
        if law.get("법령명한글") == name and law.get("현행연혁코드") == "현행":
            return law
    return laws[0] if laws else None


def fetch_articles(mst: str) -> dict:
    params = {"OC": OC, "target": "law", "MST": mst, "type": "JSON"}
    url = f"{BASE}/lawService.do?{urlencode(params)}"
    return _get(url)


def collect(topic: str, law_names: list[str]) -> None:
    out = OUT_DIR / f"{topic}.jsonl"
    print(f"[{topic}] → {out}")
    with out.open("w", encoding="utf-8") as fp:
        for name in law_names:
            print(f"  · search: {name}")
            meta = search_law(name)
            if not meta:
                print(f"    !! 검색 결과 없음")
                continue
            mst = meta.get("법령일련번호")
            articles = fetch_articles(mst)
            record = {
                "law_name": name,
                "law_id": meta.get("법령ID"),
                "mst": mst,
                "proclaimed_at": meta.get("공포일자"),
                "effective_at": meta.get("시행일자"),
                "articles": articles.get("법령", articles),
            }
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
            time.sleep(0.3)  # API rate-limit 보호
    print(f"  done.")


def main() -> None:
    for topic, names in TARGETS.items():
        collect(topic, names)
    print(f"\nall seeds → {OUT_DIR}")


if __name__ == "__main__":
    main()
