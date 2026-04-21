"""판례 인용 빈도 기반 화이트리스트 자동 랭킹.

대한민국 법원 판결문(Korean Law MCP precedent 도메인)에서
각 법령의 조문이 얼마나 자주 언급되는지 집계 → Top-N 자동 선정.

출력:
  cache/whitelist/ranking.json  (세목별 조문 빈도 원자료)
  cache/whitelist/top_by_semok.json  (세목별 Top-15 추천)
  pipeline/whitelist_evidence.md  (발표용 증거 MD)

사용:
  LAW_OC=didwjs12 python scripts/rank_articles_by_citations.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OC = os.getenv("LAW_OC", "didwjs12")
URL = f"https://korean-law-mcp.fly.dev/mcp?oc={OC}"

# 세목별 검색 쿼리 (판례 검색용)
SEMOK_QUERIES: dict[str, list[tuple[str, str]]] = {
    "세법-소득세": [("소득세법", "소득세법")],
    "세법-법인세": [("법인세법", "법인세법")],
    "세법-부가가치세": [("부가가치세법", "부가가치세법")],
    "세법-상속증여세": [
        ("상속세", "상속세 및 증여세법"),
        ("증여세", "상속세 및 증여세법"),
    ],
    "민법-계약임대차": [
        ("민법 임대차", "민법"),
        ("민법 계약", "민법"),
        ("임대차 보증금", "민법"),
    ],
    "민법-상속증여": [
        ("민법 상속", "민법"),
        ("민법 유류분", "민법"),
        ("상속 회복", "민법"),
    ],
    "노동법-임금퇴직금": [
        ("근로기준법 임금", "근로기준법"),
        ("근로기준법 퇴직금", "근로기준법"),
        ("최저임금법", "최저임금법"),
    ],
    "노동법-해고연차": [
        ("근로기준법 해고", "근로기준법"),
        ("근로기준법 연차", "근로기준법"),
        ("부당해고", "근로기준법"),
    ],
}

# 법령명 후보 (본법, 시행령/시행규칙 제외)
LAW_NAMES = {
    "소득세법",
    "법인세법",
    "부가가치세법",
    "상속세 및 증여세법",
    "상속세및증여세법",  # 공백 제거 버전
    "민법",
    "상법",
    "근로기준법",
    "근로자퇴직급여 보장법",
    "근로자퇴직급여보장법",
    "최저임금법",
}

# 조문 패턴: "법령명 [시행령|시행규칙]? 제N조[의M]?"
# 그룹: (법령명, 시행류(있으면), 조문번호, 가지번호)
ARTICLE_RE = re.compile(
    r"(소득세법|법인세법|부가가치세법|상속세\s*및\s*증여세법|상속세및증여세법|"
    r"민법|상법|근로기준법|근로자퇴직급여\s*보장법|근로자퇴직급여보장법|최저임금법)"
    r"(\s*시행(?:령|규칙))?"
    r"\s*제\s*(\d+)\s*조(?:의\s*(\d+))?"
)

PAGES_PER_QUERY = int(os.getenv("RANK_PAGES", "3"))
DISPLAY_PER_PAGE = int(os.getenv("RANK_DISPLAY", "100"))


def extract_citations(text: str, target_law: str) -> Counter:
    """텍스트에서 target_law의 조문 인용 빈도 집계 (시행령/시행규칙 제외)."""
    counts: Counter = Counter()
    target_norm = target_law.replace(" ", "")
    for m in ARTICLE_RE.finditer(text):
        law_name = m.group(1).replace(" ", "")
        is_sub = m.group(2) is not None  # 시행령·시행규칙
        if is_sub:
            continue
        if law_name != target_norm:
            # 상증세법 같이 공백 변형 체크
            if not (law_name.startswith(target_norm[:5]) and target_norm.startswith(law_name[:5])):
                continue
        art_no = m.group(3)
        sub_no = m.group(4)
        key = f"{art_no}의{sub_no}" if sub_no else art_no
        counts[key] += 1
    return counts


async def rank_one_semok(
    session: ClientSession,
    semok: str,
    queries: list[tuple[str, str]],
) -> tuple[Counter, int]:
    """세목 하나에 대해 판례 검색 → 조문 빈도 반환."""
    total_counts: Counter = Counter()
    total_hits = 0
    for q_text, target_law in queries:
        for page in range(1, PAGES_PER_QUERY + 1):
            try:
                res = await session.call_tool(
                    "search_decisions",
                    {
                        "query": q_text,
                        "domain": "precedent",
                        "display": DISPLAY_PER_PAGE,
                        "page": page,
                    },
                )
            except Exception as e:  # noqa: BLE001
                print(f"    !! {semok} '{q_text}' page={page} ERROR: {e}", flush=True)
                break
            body = ""
            if res.content:
                first = res.content[0]
                body = getattr(first, "text", "") if first else ""
            if not body or "총 0건" in body:
                break
            total_hits += 1
            counts = extract_citations(body, target_law)
            total_counts.update(counts)
            # 다음 페이지 있는지 체크 (간단히 totalCnt 초과 시 중단)
            m = re.search(r"총\s*(\d+)건", body)
            if m and int(m.group(1)) <= page * DISPLAY_PER_PAGE:
                break
        print(
            f"  · {semok} '{q_text}' → {sum(total_counts.values())} citations cumulative",
            flush=True,
        )
    return total_counts, total_hits


async def amain() -> None:
    out_dir = Path("cache/whitelist")
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, list[tuple[str, int]]] = {}
    raw: dict[str, dict[str, int]] = {}

    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"=== ranking via MCP ({len(SEMOK_QUERIES)} 세목) ===", flush=True)
            for semok, queries in SEMOK_QUERIES.items():
                print(f"\n[{semok}]", flush=True)
                counts, hits = await rank_one_semok(session, semok, queries)
                top = counts.most_common(15)
                results[semok] = top
                raw[semok] = dict(counts)
                print(f"  Top-5: {top[:5]}", flush=True)

    (out_dir / "ranking.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "top_by_semok.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ===== Markdown 증거 리포트 생성 =====
    lines = [
        "# 화이트리스트 선정 근거 — 판례 인용 빈도 랭킹",
        "",
        "**출처**: Korean Law MCP `search_decisions` (domain=`precedent`) — 대한민국 법원 판결문",
        "",
        f"**수집 설정**: 세목당 {PAGES_PER_QUERY}페이지 × {DISPLAY_PER_PAGE}건 (최대 {PAGES_PER_QUERY * DISPLAY_PER_PAGE}건/쿼리)",
        "",
        "**집계 방법**: 판례 요약 본문에서 `법령명 제N조` 패턴 regex 추출 → 조문별 빈도 합계 (시행령·시행규칙 제외)",
        "",
        "---",
        "",
    ]
    for semok, top in results.items():
        lines.append(f"## {semok}")
        lines.append("")
        lines.append(f"**쿼리**: {', '.join(q for q, _ in SEMOK_QUERIES[semok])}")
        lines.append("")
        lines.append("| 순위 | 조문 | 판례 인용 빈도 |")
        lines.append("|---|---|:---:|")
        for i, (art, cnt) in enumerate(top, 1):
            lines.append(f"| {i} | 제{art}조 | {cnt} |")
        lines.append("")
    (Path("pipeline/whitelist_evidence.md")).write_text(
        "\n".join(lines), encoding="utf-8"
    )

    # ===== pipeline/seeds.py 자동 갱신 제안 출력 =====
    print("\n=== 자동 추출 Top-8 (seeds.py 갱신 후보) ===")
    print("SEMOK_KEY_ARTICLES: dict[str, list[str]] = {")
    for semok, top in results.items():
        top8 = [art for art, _ in top[:8]]
        print(f'    "{semok}": {json.dumps(top8, ensure_ascii=False)},')
    print("}")

    print(
        f"\n=== DONE ===\n"
        f"  raw:    cache/whitelist/ranking.json\n"
        f"  top:    cache/whitelist/top_by_semok.json\n"
        f"  evid:   pipeline/whitelist_evidence.md"
    )


if __name__ == "__main__":
    asyncio.run(amain())
