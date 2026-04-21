"""민법·노동법 개념어 기반 2차 랭킹.

1차(rank_articles_by_citations)에서 '민법 임대차', '근로기준법 해고' 같은
법령+주제 쿼리로는 빈도 부족. 이번엔 **법학 개념어 단독**으로 판례 검색 후
본문에서 법령 조문 추출.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OC = os.getenv("LAW_OC", "didwjs12")
URL = f"https://korean-law-mcp.fly.dev/mcp?oc={OC}"

# 개념어 쿼리 (민법·노동법 주요 쟁점) → 본문에서 법령 조문 추출
SEMOK_CONCEPT_QUERIES: dict[str, tuple[list[str], str]] = {
    "민법-계약임대차": (
        [
            "임대차 계약 해지",
            "임대차 보증금 반환",
            "계약 해제 손해배상",
            "차임 연체",
            "전세권 설정",
            "권리금 회수",
        ],
        "민법",
    ),
    "민법-상속증여": (
        [
            "법정상속",
            "유류분 반환",
            "상속 포기",
            "상속 한정승인",
            "증여 계약",
            "재산분할",
            "상속재산 분할",
        ],
        "민법",
    ),
    "노동법-임금퇴직금": (
        [
            "통상임금",
            "연장근로 수당",
            "퇴직금 지급",
            "퇴직급여 중간정산",
            "임금 체불",
            "최저임금",
        ],
        "근로기준법",
    ),
    "노동법-해고연차": (
        [
            "정당한 해고",
            "부당해고 구제",
            "경영상 해고",
            "연차유급휴가",
            "해고예고",
            "징계해고",
        ],
        "근로기준법",
    ),
}

ARTICLE_RE = re.compile(
    r"(민법|근로기준법|근로자퇴직급여\s*보장법|근로자퇴직급여보장법|최저임금법)"
    r"(\s*시행(?:령|규칙))?"
    r"\s*제\s*(\d+)\s*조(?:의\s*(\d+))?"
)

PAGES = int(os.getenv("R2_PAGES", "2"))
DISPLAY = int(os.getenv("R2_DISPLAY", "100"))


def extract(text: str, target_law: str) -> Counter:
    counts: Counter = Counter()
    tn = target_law.replace(" ", "")
    for m in ARTICLE_RE.finditer(text):
        law = m.group(1).replace(" ", "")
        if m.group(2):
            continue
        if law != tn:
            continue
        no = m.group(3)
        sub = m.group(4)
        key = f"{no}의{sub}" if sub else no
        counts[key] += 1
    return counts


async def amain() -> None:
    out_dir = Path("cache/whitelist")
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, list[tuple[str, int]]] = {}
    raw: dict[str, dict[str, int]] = {}

    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"=== round 2: 개념어 랭킹 ({len(SEMOK_CONCEPT_QUERIES)} 세목) ===", flush=True)
            for semok, (queries, target_law) in SEMOK_CONCEPT_QUERIES.items():
                print(f"\n[{semok}] (target={target_law})", flush=True)
                total_counts: Counter = Counter()
                for q in queries:
                    for page in range(1, PAGES + 1):
                        try:
                            res = await session.call_tool(
                                "search_decisions",
                                {
                                    "query": q,
                                    "domain": "precedent",
                                    "display": DISPLAY,
                                    "page": page,
                                },
                            )
                        except Exception as e:
                            print(f"    !! '{q}' page={page} ERROR: {e}", flush=True)
                            break
                        body = ""
                        if res.content:
                            first = res.content[0]
                            body = getattr(first, "text", "") if first else ""
                        if not body or "총 0건" in body:
                            break
                        total_counts.update(extract(body, target_law))
                        m = re.search(r"총\s*(\d+)건", body)
                        if m and int(m.group(1)) <= page * DISPLAY:
                            break
                    print(f"  · '{q}' → {sum(total_counts.values())} citations", flush=True)
                top = total_counts.most_common(15)
                results[semok] = top
                raw[semok] = dict(total_counts)
                print(f"  Top-8: {top[:8]}", flush=True)

    (out_dir / "ranking_round2.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== ROUND2 자동 Top-8 ===")
    print("SEMOK_KEY_ARTICLES (민법·노동법 갱신 후보):")
    for semok, top in results.items():
        top8 = [art for art, _ in top[:8]]
        print(f'    "{semok}": {json.dumps(top8, ensure_ascii=False)},')


if __name__ == "__main__":
    asyncio.run(amain())
