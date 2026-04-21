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
    # 소득세법: 근로소득(20)·종합소득(24)·근로공제(47)·연금계좌공제(47의2)·기본공제(51)·특별공제(52)·세율(55)·세액공제(59)·원천징수(129)
    "세법-소득세": ["20", "24", "47", "47의2", "51", "52", "55", "59", "129"],
    # 법인세법: 과세소득(13)·손금(15,19)·익금불산입(16의2)·감가상각(23)·기부금(25)·세율(55)·세무조정(66)·원천징수(76)
    "세법-법인세": ["13", "15", "16의2", "19", "23", "25", "55", "66", "76"],
    # 부가가치세법: 납세의무자(3)·과세대상(4,11)·과세표준(26,29)·세율(30)·매입세액공제(37,38,39)
    "세법-부가가치세": ["3", "4", "11", "26", "29", "37", "38", "39"],
    # 상증세법: 과세대상(3,13)·증여의제(45의2)·배우자공제(18,53)·평가(60,63)·가업상속공제(18의2)·명의신탁(45의2)
    "세법-상속증여세": ["3", "13", "18", "18의2", "33", "44", "45의2", "53", "60", "63"],
    # 민법 계약·임대차: 채무불이행 손해배상(390)·동시이행(536)·매매(568)·임대차(618·623·627·635·639)·도급(664)
    "민법-계약임대차": ["390", "536", "568", "618", "623", "627", "635", "639", "664"],
    # 민법 상속·증여: 증여(554)·상속순위(1000·1001)·단순승인(1005)·분묘(1008)·법정상속분(1009)·유류분(1112·1113)·대습상속(1001)·재산분할청구권(839의2)
    "민법-상속증여": ["554", "839의2", "1000", "1001", "1005", "1008", "1009", "1112", "1113"],
    # 근로기준법·최저임금법·퇴직급여보장법: 임금(2·43)·휴업수당(46)·연장근로 가산(56)·퇴직금(34·34의2)·최저임금·중간정산(퇴직급여법)
    "노동법-임금퇴직금": ["2", "34", "34의2", "36", "43", "46", "56", "57", "60"],
    # 근로기준법 해고·연차: 해고제한(23·24)·해고예고(26·27)·부당해고 구제(28)·연차(60)·임산부(75)·벌칙(111)
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
