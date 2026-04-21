"""B1 — NVIDIA Build API (Super 120B) 교차 검증.

Nano가 생성한 reasoning_cot에서 조문 추출 vs
Super 120B가 같은 question에 답했을 때의 조문 추출
→ 교집합/합집합 = cross_overlap (Jaccard)
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from .. import cache as _cache


BUILD_API_URL = "https://integrate.api.nvidia.com/v1"
BUILD_API_KEY = os.getenv("NVIDIA_BUILD_API_KEY", "")
BUILD_MODEL = os.getenv(
    "BUILD_MODEL", "nvidia/nemotron-3-super-120b-a12b"
)
DEFAULT_MAX_TOKENS = int(os.getenv("BUILD_MAX_TOKENS", "1024"))


# 조문 인용 regex (예: "소득세법 제20조", "민법 제618조의2")
_LAW_PATTERNS = [
    r"(소득세법|법인세법|부가가치세법|상속세및증여세법|상속세 및 증여세법|"
    r"민법|상법|형법|근로기준법|최저임금법|근로자퇴직급여보장법|"
    r"근로자퇴직급여 보장법)"
    r"(\s*시행(령|규칙))?\s*제\s*(\d+)\s*조(의\s*\d+)?",
]


def extract_law_refs(text: str) -> set[str]:
    """텍스트에서 법령 조문 참조 정규화 추출. 공백 제거, 소문자 통일."""
    refs: set[str] = set()
    if not text:
        return refs
    for pat in _LAW_PATTERNS:
        for m in re.finditer(pat, text):
            law = m.group(1).replace(" ", "")
            suffix = m.group(2) or ""
            art_no = m.group(4)
            sub = m.group(5) or ""
            ref = f"{law}{suffix}_제{art_no}조{sub.replace(' ', '')}"
            refs.add(ref)
    return refs


@dataclass
class CrossResult:
    nano_refs: list[str] = field(default_factory=list)
    super_refs: list[str] = field(default_factory=list)
    common: list[str] = field(default_factory=list)
    nano_only: list[str] = field(default_factory=list)
    super_only: list[str] = field(default_factory=list)
    cross_overlap: float = 0.0  # Jaccard
    super_cot_head: str = ""

    def to_dict(self) -> dict:
        return {
            "cross_overlap": self.cross_overlap,
            "cross_nano_refs": self.nano_refs,
            "cross_super_refs": self.super_refs,
            "cross_common": self.common,
            "cross_nano_only": self.nano_only,
            "cross_super_only": self.super_only,
            "super_cot_head": self.super_cot_head,
        }


async def call_super_once(
    client: AsyncOpenAI,
    question: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.3,
) -> str:
    """Super 120B에 질문 1건 보내고 응답 텍스트 반환 (reasoning 포함)."""
    resp = await client.chat.completions.create(
        model=BUILD_MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "당신은 한국 법률 전문가입니다. 다음 질문에 적용 조문 중심으로 답하세요.\n\n"
                    f"질문: {question}\n\n"
                    "지침: 관련 법령과 조문 번호를 명시적으로 인용하세요."
                ),
            }
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    msg = resp.choices[0].message
    # Build API는 reasoning/content 합쳐 content에 담음
    return msg.content or ""


async def cross_verify_one(
    question: str,
    reasoning_cot: str,
    *,
    client: AsyncOpenAI | None = None,
    use_cache: bool = True,
) -> CrossResult:
    nano_refs = extract_law_refs(reasoning_cot)

    # 캐시 키: question (같은 질문은 답변이 유사)
    cache_key = f"build_super_{BUILD_MODEL.split('/')[-1]}"
    cached_super_text: str | None = None
    if use_cache:
        cached = _cache.get(cache_key, question)
        if cached is not None:
            cached_super_text = cached.get("text", "")

    if cached_super_text is None:
        close_client = False
        if client is None:
            client = AsyncOpenAI(base_url=BUILD_API_URL, api_key=BUILD_API_KEY)
            close_client = True
        try:
            cached_super_text = await call_super_once(client, question)
        finally:
            if close_client:
                await client.close()
        if use_cache:
            _cache.put(cache_key, question, {"text": cached_super_text})

    super_refs = extract_law_refs(cached_super_text)

    union = nano_refs | super_refs
    common = nano_refs & super_refs
    nano_only = nano_refs - super_refs
    super_only = super_refs - nano_refs

    jaccard = len(common) / len(union) if union else 0.0
    return CrossResult(
        nano_refs=sorted(nano_refs),
        super_refs=sorted(super_refs),
        common=sorted(common),
        nano_only=sorted(nano_only),
        super_only=sorted(super_only),
        cross_overlap=jaccard,
        super_cot_head=cached_super_text[:400],
    )


async def cross_verify_batch(
    items: list[tuple[str, str]],
    *,
    concurrency: int = 4,
) -> list[CrossResult]:
    """items = [(question, reasoning_cot), ...]"""
    if not BUILD_API_KEY:
        raise RuntimeError(
            "NVIDIA_BUILD_API_KEY 환경변수가 필요합니다. .env에 설정하세요."
        )

    sem = asyncio.Semaphore(concurrency)
    client = AsyncOpenAI(base_url=BUILD_API_URL, api_key=BUILD_API_KEY)
    results: list[CrossResult] = [CrossResult() for _ in items]

    async def _one(i: int, q: str, c: str) -> None:
        async with sem:
            try:
                results[i] = await cross_verify_one(q, c, client=client)
            except Exception as e:  # noqa: BLE001
                r = CrossResult()
                r.super_cot_head = f"ERROR: {type(e).__name__}: {e}"
                results[i] = r

    try:
        await asyncio.gather(
            *[_one(i, q, c) for i, (q, c) in enumerate(items)]
        )
    finally:
        await client.close()
    return results
