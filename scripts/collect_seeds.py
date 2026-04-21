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


# 도메인 → 대상 법령 목록
TARGETS = {
    # === 세법 (기존 4) ===
    "income_tax": ["소득세법", "소득세법 시행령", "소득세법 시행규칙"],
    "corporate_tax": ["법인세법", "법인세법 시행령"],
    "vat": ["부가가치세법", "부가가치세법 시행령"],
    "inheritance_gift_tax": ["상속세 및 증여세법", "상속세 및 증여세법 시행령"],
    # === 민법 (신규) ===
    "civil_contract": ["민법"],  # 전체 민법 1건 — 계약/임대차 조항 포함
    "civil_inheritance": ["민법"],  # 상속편 별도 토픽 — 같은 법률을 도메인 축에서만 분기
    # === 노동법 (신규) ===
    "labor_wage": ["근로기준법", "근로기준법 시행령", "최저임금법"],
    "labor_dismissal": ["근로기준법", "근로자퇴직급여 보장법"],
}


def _get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "track-c-seed-collector/0.1"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_law(name: str) -> dict | None:
    """정확 일치만 허용. 부분 일치(예: '민법' 검색 시 '난민법' 반환) 방지."""
    params = {
        "OC": OC,
        "target": "law",
        "query": name,
        "type": "JSON",
        "display": 10,  # 상위 10개 받아서 정확 일치 찾기
    }
    url = f"{BASE}/lawSearch.do?{urlencode(params)}"
    data = _get(url)
    laws = data.get("LawSearch", {}).get("law") or []
    if isinstance(laws, dict):
        laws = [laws]
    # 1) 현행 + 정확 이름 일치
    for law in laws:
        if law.get("법령명한글") == name and law.get("현행연혁코드") == "현행":
            return law
    # 2) 현행 중 정확 일치 (어느 연혁이든)
    for law in laws:
        if law.get("법령명한글") == name:
            return law
    # 3) 정확 일치 없으면 경고 로그 후 None (이전의 "laws[0] 폴백" 제거)
    print(
        f"    !! '{name}' 정확 일치 없음. 상위 후보: "
        + ", ".join(l.get("법령명한글", "?") for l in laws[:3])
    )
    return None


def fetch_articles(mst: str) -> dict:
    params = {"OC": OC, "target": "law", "MST": mst, "type": "JSON"}
    url = f"{BASE}/lawService.do?{urlencode(params)}"
    return _get(url)


_CACHE_DIR = OUT_DIR.parent / "law_raw"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_law_record(name: str) -> dict | None:
    """법률 1개 전체 조문 수집 (dedup 캐시 사용)."""
    cache_path = _CACHE_DIR / f"{name}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    meta = search_law(name)
    if not meta:
        return None
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
    cache_path.write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )
    time.sleep(0.3)
    return record


def collect(topic: str, law_names: list[str]) -> None:
    out = OUT_DIR / f"{topic}.jsonl"
    print(f"[{topic}] → {out}")
    with out.open("w", encoding="utf-8") as fp:
        for name in law_names:
            print(f"  · search: {name}")
            rec = _fetch_law_record(name)
            if not rec:
                print(f"    !! 검색 결과 없음")
                continue
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  done.")


def main() -> None:
    for topic, names in TARGETS.items():
        collect(topic, names)
    print(f"\nall seeds → {OUT_DIR}")
    print(f"law raw cache → {_CACHE_DIR}")


if __name__ == "__main__":
    main()
