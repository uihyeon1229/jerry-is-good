"""Korean Law MCP verify_citations 래퍼 (L2).

응답은 텍스트 기반이므로 패턴 매칭으로 수치 추출.

예시 응답 헤더:
    [HALLUCINATION_DETECTED] == 인용 검증 결과 ==
    총 3건 | ✓ 1 실존 | ✗ 1 오류 | ⚠ 1 확인필요

    ⚠ 답변은 소득세법 제20조 — 법제처 검색은 '소득세법'(으)로만 매칭됨. 법령명 정확성 재확인 필요
    ✓ 소득세법 제47조(근로소득공제) 실존
    ✗ 부가가치세법 제999조 — [NOT_FOUND] 해당 조문 없음 (존재 범위: 제1조~제76조)
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .. import cache as _cache


DEFAULT_URL = os.getenv(
    "LAW_MCP_URL",
    f"https://korean-law-mcp.fly.dev/mcp?oc={os.getenv('LAW_OC', 'didwjs12')}",
)
DEFAULT_MAX_CITATIONS = int(os.getenv("LAW_MCP_MAX_CITATIONS", "15"))


@dataclass
class CitationResult:
    total: int = 0
    valid: int = 0
    warning: int = 0
    invalid: int = 0
    has_hallucination: bool = False
    invalid_refs: list[str] = field(default_factory=list)
    warning_refs: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def valid_ratio(self) -> float:
        if self.total == 0:
            return 0.0
        return self.valid / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "cited_laws_total": self.total,
            "cited_laws_valid": self.valid,
            "cited_laws_warning": self.warning,
            "cited_laws_invalid": self.invalid,
            "cited_laws_valid_ratio": self.valid_ratio,
            "has_hallucination": self.has_hallucination,
            "invalid_refs": self.invalid_refs,
            "warning_refs": self.warning_refs,
        }


# ---- 텍스트 응답 파싱 --------------------------------------------------------

_HEADER_RE = re.compile(
    r"총\s*(\d+)\s*건\s*\|\s*✓\s*(\d+)\s*실존\s*\|\s*✗\s*(\d+)\s*오류\s*\|\s*⚠\s*(\d+)\s*확인필요"
)
_INVALID_LINE_RE = re.compile(r"^✗\s*(.+?)\s+—\s+", re.MULTILINE)
_WARNING_LINE_RE = re.compile(r"^⚠\s*(.+?)(?:\s+—|$)", re.MULTILINE)


def parse_verify_response(text: str) -> CitationResult:
    r = CitationResult(raw=text)
    r.has_hallucination = "[HALLUCINATION_DETECTED]" in text

    m = _HEADER_RE.search(text)
    if m:
        r.total, r.valid, r.invalid, r.warning = map(int, m.groups())

    for m in _INVALID_LINE_RE.finditer(text):
        r.invalid_refs.append(m.group(1).strip())
    for m in _WARNING_LINE_RE.finditer(text):
        ref = m.group(1).strip()
        # "[HALLUCINATION_DETECTED]" 같은 헤더 노이즈 제거
        if ref and not ref.startswith("[") and "항목은" not in ref:
            r.warning_refs.append(ref)

    return r


# ---- 단일/배치 검증 ---------------------------------------------------------


async def verify_text(
    session: ClientSession,
    text: str,
    max_citations: int = DEFAULT_MAX_CITATIONS,
    *,
    use_cache: bool = True,
) -> CitationResult:
    if not text or not text.strip():
        return CitationResult()

    cache_key = f"verify_citations_mc{max_citations}"
    if use_cache:
        cached = _cache.get(cache_key, text)
        if cached is not None:
            r = CitationResult(
                total=cached.get("cited_laws_total", 0),
                valid=cached.get("cited_laws_valid", 0),
                warning=cached.get("cited_laws_warning", 0),
                invalid=cached.get("cited_laws_invalid", 0),
                has_hallucination=cached.get("has_hallucination", False),
                invalid_refs=list(cached.get("invalid_refs", [])),
                warning_refs=list(cached.get("warning_refs", [])),
                raw=cached.get("_raw", ""),
            )
            return r

    resp = await session.call_tool(
        "verify_citations",
        {"text": text, "maxCitations": max_citations},
    )
    body = ""
    if resp.content:
        first = resp.content[0]
        body = getattr(first, "text", str(first))
    result = parse_verify_response(body)

    if use_cache:
        payload = result.to_dict()
        payload["_raw"] = result.raw[:500]
        _cache.put(cache_key, text, payload)

    return result


async def verify_batch(
    texts: list[str],
    *,
    url: str = DEFAULT_URL,
    max_citations: int = DEFAULT_MAX_CITATIONS,
    concurrency: int = 8,
) -> list[CitationResult]:
    """여러 텍스트를 한 세션으로 병렬 검증."""
    results: list[CitationResult] = [CitationResult() for _ in texts]
    sem = asyncio.Semaphore(concurrency)

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def _one(i: int, t: str) -> None:
                async with sem:
                    try:
                        results[i] = await verify_text(session, t, max_citations)
                    except Exception as e:  # noqa: BLE001
                        r = CitationResult()
                        r.raw = f"ERROR: {type(e).__name__}: {e}"
                        results[i] = r

            await asyncio.gather(*[_one(i, t) for i, t in enumerate(texts)])

    return results
