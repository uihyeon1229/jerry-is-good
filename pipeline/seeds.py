"""법제처 시드 JSONL → 세목별 조문 텍스트 (L1 context 주입용).

cache/seeds/{세목}.jsonl 각 파일은 여러 법령(법·시행령·시행규칙)의 전체 조문을 포함.

세목별 **실질 조문 화이트리스트**(SEMOK_KEY_ARTICLES)를 우선 선택하고,
부족하면 총칙을 제외한 조문 번호 오름차순으로 채움.
(v2.1 교훈: 총칙 제1조·제2조만 뽑으면 실무 CoT 불가능)
"""

from __future__ import annotations

import json
import re
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
# "47의2" 형식으로 **가지 조문**도 지정 가능 (개정 시 끼워넣은 조문).
# 각 키는 "본조번호" 또는 "본조번호의가지번호" 문자열.
# 선정 근거: C 담당 실무자 빈도 + 공통 민원 주제.
SEMOK_KEY_ARTICLES: dict[str, list[str]] = {
    # ==========================================================================
    # 세법 4세목: Korean Law MCP 판례 빈도 Top-8 자동 추출 + 실무 Top-4 병합
    # (근거: pipeline/whitelist_evidence.md, search_decisions precedent 도메인)
    # ==========================================================================
    # 소득세법 판례 빈도 Top: §97(양도소득)·§20(근로소득)·§100(양도가액)·§114의2(가산세)
    # + 실무 핵심 §47(근로소득공제)·§47의2(연금계좌)·§51(기본공제)·§52(특별공제)·§55(세율)
    "세법-소득세": ["97", "20", "100", "114의2", "47", "47의2", "55", "51", "52"],
    # 법인세법 판례 빈도 Top: §52(부당행위계산부인)·§18의2(외국납부세액공제)·§18·§93·§19
    # + 실무 핵심 §15(손금)·§23(감가상각)·§55(세율)·§66(세무조정)
    "세법-법인세": ["52", "18의2", "18", "19", "15", "23", "55", "66", "93"],
    # 부가가치세법 판례 빈도 Top: §22(매입세액 공제제한)·§29(과세표준)·§39(매입세액불공제)
    # + 실무 핵심 §3(납세의무)·§11(공급장소)·§37(납부세액)·§38(공제)
    "세법-부가가치세": ["22", "29", "39", "3", "11", "37", "38", "17"],
    # 상증세법 판례 빈도 Top: §60(재산평가)·§38(합병이익 증여)·§45의2(명의신탁)·§42·§45
    # + 실무 핵심 §13(과세가액)·§18(기초공제)·§53(배우자공제)·§63(상장주식 평가)
    "세법-상속증여세": ["60", "38", "45의2", "42", "45", "13", "18", "53", "63"],
    # ==========================================================================
    # 민법·노동법 4세목: 실무자(C 담당) 선정 + 법학 교과서 핵심 주제
    # MCP 판례 빈도 집계는 본문에 조문 번호 직접 인용이 드물어(한국 판례 작성 관행) 자동 랭킹 부적합.
    # 2026-04-21 확인: 4세목 모두 판례 빈도 < 5 → 실무자 판단으로 대체 (whitelist_evidence.md §B 참조)
    # ==========================================================================
    # 민법 계약·임대차: 채무불이행(390)·동시이행(536)·매매(568)·임대차(618·623·627·635·639)
    "민법-계약임대차": ["390", "536", "568", "618", "623", "627", "635", "639", "664"],
    # 민법 상속·증여: 증여(554)·재산분할청구권(839의2)·법정상속(1000·1009)·유류분(1112·1113)
    "민법-상속증여": ["554", "839의2", "1000", "1001", "1005", "1008", "1009", "1112", "1113"],
    # 근로기준법: 임금(2·43)·연장근로 가산(56)·퇴직금(34·34의2)·휴업수당(46)
    "노동법-임금퇴직금": ["2", "34", "34의2", "36", "43", "46", "56", "57", "60"],
    # 근로기준법: 해고제한(23·24)·해고예고(26·27)·부당해고 구제(28)·연차(60)
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


def _article_key(art: dict) -> str:
    """조문번호 + 조문가지번호 → '47' 또는 '47의2' 형식."""
    no = str(art.get("조문번호") or "").strip()
    sub = art.get("조문가지번호")
    if not no:
        return ""
    if sub is not None and str(sub).strip():
        return f"{no}의{sub}"
    return no


def _index_articles(records: list[dict]) -> dict[str, tuple[str, dict]]:
    """조문 키('47' 또는 '47의2') → (law_name, article). 본법 우선."""
    sorted_records = sorted(
        records,
        key=lambda r: ("시행령" in (r.get("law_name") or ""))
        + 2 * ("시행규칙" in (r.get("law_name") or "")),
    )
    idx: dict[str, tuple[str, dict]] = {}
    for rec in sorted_records:
        law_name = rec.get("law_name") or ""
        for art in _extract_articles(rec):
            key = _article_key(art)
            if not key:
                continue
            if key not in idx:  # 본법이 먼저 등록 (override 방지)
                idx[key] = (law_name, art)
    return idx


_KEY_RE = re.compile(r"^(\d+)(?:의(\d+))?$")


def _num_key(s: str) -> tuple[int, int]:
    """'47' → (47, 0), '47의2' → (47, 2). 정렬용 튜플."""
    m = _KEY_RE.match(s)
    if not m:
        return (999999, 0)
    return (int(m.group(1)), int(m.group(2) or 0))


@lru_cache(maxsize=None)
def seed_context_for(
    semok: str,
    *,
    top_n: int = 5,
    max_content_chars: int = 1000,
) -> str:
    """세목 → 프롬프트에 주입할 조문 context 문자열.

    1) SEMOK_KEY_ARTICLES 화이트리스트 우선 (가지 조문 '47의2' 지원)
    2) 부족 시 총칙(제1~2조) 제외하고 (본조번호, 가지번호) 튜플 순 채움
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

    # 2) 부족 시 총칙 제외하고 번호 순으로 채움 (가지 조문 포함)
    if len(selected) < top_n:
        GENERAL_SKIP = {"1", "2"}
        for no in sorted(idx.keys(), key=_num_key):
            if no in used or no in GENERAL_SKIP:
                continue
            selected.append(idx[no])
            used.add(no)
            if len(selected) >= top_n:
                break

    lines = [_format_article(ln, art, max_content_chars) for ln, art in selected]
    return "\n".join(lines)
