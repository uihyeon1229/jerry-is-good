"""법제처 시드 JSONL → 세목별 조문 텍스트 (L1 context 주입용).

cache/seeds/{income_tax,corporate_tax,vat,inheritance_gift_tax}.jsonl
각 파일은 여러 법령(법·시행령·시행규칙)의 전체 조문을 포함.

우리는 각 세목마다 **Top-N개 조문**을 context로 주입. Top-N 선정 로직은
일단 간단히 "실제 조문만(조문여부='조문') + 조문번호 오름차순" 기반 N=5.
나중에 중요도 수동 지정 가능.
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


@lru_cache(maxsize=None)
def seed_context_for(
    semok: str,
    *,
    top_n: int = 5,
    max_content_chars: int = 400,
) -> str:
    """세목 → 프롬프트에 주입할 조문 context 문자열."""
    seed_file = SEMOK_TO_SEED_FILE.get(semok)
    if not seed_file:
        return ""
    path = settings.seed_dir / f"{seed_file}.jsonl"
    if not path.exists():
        return ""

    lines: list[str] = []
    for law_record in _load_law_file(path):
        law_name = law_record.get("law_name") or ""
        # 시행령·시행규칙은 제외하고 본법만 우선 (Top-N 안에 본법이 먼저 들어가도록)
        if "시행령" in law_name or "시행규칙" in law_name:
            continue
        articles = _extract_articles(law_record)
        for art in articles[:top_n]:
            lines.append(_format_article(law_name, art, max_content_chars))

    # 시행령에서도 주요 조문 몇 개 추가 (법본법 후순위)
    if len(lines) < top_n:
        for law_record in _load_law_file(path):
            law_name = law_record.get("law_name") or ""
            if "시행령" not in law_name:
                continue
            articles = _extract_articles(law_record)
            for art in articles[: max(top_n - len(lines), 0)]:
                lines.append(_format_article(law_name, art, max_content_chars))
            break

    return "\n".join(lines[:top_n])
