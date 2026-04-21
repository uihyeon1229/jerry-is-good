"""법제처 시드 JSONL → 세목별 조문 텍스트 (L1 context 주입용).

cache/seeds/{세목}.jsonl 각 파일은 여러 법령(법·시행령·시행규칙)의 전체 조문을 포함.

세목별 **실질 조문 화이트리스트**(SEMOK_KEY_ARTICLES)를 우선 선택하고,
부족하면 총칙을 제외한 조문 번호 오름차순으로 채움.
(v2.1 교훈: 총칙 제1조·제2조만 뽑으면 실무 CoT 불가능)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .settings import settings


# 세목(Sampler 값) → 시드 파일 매핑 (v2.1: 8세부 3도메인)
SEMOK_TO_SEED_FILE: dict[str, str] = {
    # 세법
    "세법-소득세": "income_tax",
    "세법-법인세": "corporate_tax",
    "세법-부가가치세": "vat",
    "세법-상속증여세": "inheritance_gift_tax",
    # 민법 (같은 파일 공유, 토픽이 프롬프트 맥락만 분기)
    "민법-계약임대차": "civil_contract",
    "민법-상속증여": "civil_inheritance",
    # 노동법
    "노동법-임금퇴직금": "labor_wage",
    "노동법-해고연차": "labor_dismissal",
}


# 세목별 실질 조문 화이트리스트 (조문번호 우선순위, 실무 빈도 기반)
# 이 목록에 있는 조문을 먼저 Top-N에 채우고, 부족하면 총칙 제외하고 추가
SEMOK_KEY_ARTICLES: dict[str, list[str]] = {
    "세법-소득세": ["20", "24", "47", "51", "52", "55", "59", "129"],
    "세법-법인세": ["13", "15", "19", "23", "25", "55", "66", "76"],
    "세법-부가가치세": ["3", "4", "11", "26", "29", "37", "38", "39"],
    "세법-상속증여세": ["3", "13", "18", "33", "44", "53", "60", "63"],
    "민법-계약임대차": ["390", "568", "618", "623", "627", "635", "639", "664"],
    "민법-상속증여": ["554", "1000", "1001", "1005", "1008", "1009", "1112", "1113"],
    "노동법-임금퇴직금": ["2", "34", "36", "43", "46", "56", "57", "60"],
    "노동법-해고연차": ["23", "24", "26", "27", "28", "60", "75", "111"],
}


def _extract_articles(raw: dict) -> list[dict]:
    """한 법령 JSON에서 실제 조문들(조문여부='조문')만 반환."""
    arts = raw.get("articles") or {}
    outer = arts.get("조문") or {}
    units = outer.get("조문단위")
    if isinstance(units, list) and units and isinstance(units[0], list):
        # 파이프라인 버전에 따라 list[list[dict]] 형태로 오는 경우
        flat: list[dict] = []
        for chunk in units:
            if isinstance(chunk, list):
                flat.extend(chunk)
        units = flat
    if not isinstance(units, list):
        return []
    return [u for u in units if isinstance(u, dict) and u.get("조문여부") == "조문"]


def _format_article(law_name: str, art: dict, max_content_chars: int) -> str:
    no = art.get("조문번호")
    title = art.get("조문제목") or ""
    content = (art.get("조문내용") or "").strip()
    head = f"{law_name} 제{no}조"
    if title:
        head += f"({title})"
    if len(content) > max_content_chars:
        content = content[:max_content_chars] + "…"
    return f"- {head}: {content}"


def _load_law_file(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fp:
        return [json.loads(line) for line in fp if line.strip()]


def _index_articles(records: list[dict]) -> dict[str, tuple[str, dict]]:
    """조문번호 → (law_name, article). 본법 우선, 동일 번호면 본법이 먼저."""
    # 본법 먼저, 시행령/시행규칙 나중
    sorted_records = sorted(
        records,
        key=lambda r: ("시행령" in (r.get("law_name") or ""))
        + 2 * ("시행규칙" in (r.get("law_name") or "")),
    )
    idx: dict[str, tuple[str, dict]] = {}
    for rec in sorted_records:
        law_name = rec.get("law_name") or ""
        for art in _extract_articles(rec):
            no = str(art.get("조문번호") or "")
            if not no:
                continue
            if no not in idx:  # 본법 먼저 등록됐으므로 덮어쓰지 않음
                idx[no] = (law_name, art)
    return idx


@lru_cache(maxsize=None)
def seed_context_for(
    semok: str,
    *,
    top_n: int = 5,
    max_content_chars: int = 400,
) -> str:
    """세목 → 프롬프트에 주입할 조문 context 문자열.

    1) SEMOK_KEY_ARTICLES 화이트리스트 우선
    2) 부족하면 총칙(제1~2조) 제외 조문 번호 오름차순으로 채움
    """
    seed_file = SEMOK_TO_SEED_FILE.get(semok)
    if not seed_file:
        return ""
    path = settings.seed_dir / f"{seed_file}.jsonl"
    if not path.exists():
        return ""

    records = _load_law_file(path)
    idx = _index_articles(records)

    selected: list[tuple[str, dict]] = []
    used: set[str] = set()

    # 1) 화이트리스트 우선
    for no in SEMOK_KEY_ARTICLES.get(semok, []):
        if no in idx and no not in used:
            selected.append(idx[no])
            used.add(no)
            if len(selected) >= top_n:
                break

    # 2) 부족 시 총칙 제외 조문으로 채움
    if len(selected) < top_n:
        GENERAL_SKIP = {"1", "2"}  # 목적·정의
        # 조문번호 숫자 정렬
        def _num(s: str) -> int:
            try:
                return int("".join(ch for ch in s if ch.isdigit()) or "999999")
            except ValueError:
                return 999999

        for no in sorted(idx.keys(), key=_num):
            if no in used or no in GENERAL_SKIP:
                continue
            selected.append(idx[no])
            used.add(no)
            if len(selected) >= top_n:
                break

    lines = [_format_article(ln, art, max_content_chars) for ln, art in selected]
    return "\n".join(lines)
