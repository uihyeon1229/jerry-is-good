"""NeMo Data Designer 5건 smoke test (data-designer 0.5.7 호환).

- Sampler 2축 (세목 × 난이도)
- LLMTextColumn 1개 (reasoning_cot)
- vLLM Nemotron 엔드포인트 사용 (port 5000)
- preview로 먼저 돌려 확인
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from data_designer.interface import DataDesigner
from data_designer.config import (
    DataDesignerConfigBuilder,
    ModelProvider,
    ModelConfig,
    ChatCompletionInferenceParams,
    SamplerColumnConfig,
    SamplerType,
    CategorySamplerParams,
    LLMTextColumnConfig,
)

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
MODEL_NAME = os.getenv("VLLM_MODEL", "nemotron")
NUM_ROWS = int(os.getenv("SMOKE_N", "5"))
OUT_PATH = Path(os.getenv("SMOKE_OUT", "/home/shadeform/jerry-is-good/output/smoke/dd_5.jsonl"))
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

provider = ModelProvider(
    name="local_vllm",
    endpoint=BASE_URL,
    provider_type="openai",
    api_key="not-used",
)

model = ModelConfig(
    alias="nemotron",
    model=MODEL_NAME,
    provider="local_vllm",
    inference_parameters=ChatCompletionInferenceParams(
        temperature=0.7,
        max_tokens=int(__import__("os").getenv("SMOKE_MAX_TOKENS", "8192")),
    ),
)

builder = DataDesignerConfigBuilder()
builder.add_model_config(model)

builder.add_column(
    SamplerColumnConfig(
        name="세목",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(
            values=["소득세-근로소득", "법인세-세무조정", "부가가치세-매입세액공제"],
        ),
    )
)
builder.add_column(
    SamplerColumnConfig(
        name="난이도",
        sampler_type=SamplerType.CATEGORY,
        params=CategorySamplerParams(values=["기초", "중급", "고급"]),
    )
)

builder.add_column(
    LLMTextColumnConfig(
        name="reasoning_cot",
        prompt=(
            "당신은 한국 세법 전문가입니다.\n"
            "세목: {{ 세목 }}\n"
            "난이도: {{ 난이도 }}\n\n"
            "해당 조건에 맞는 납세자 질문을 하나 만들고, "
            "적용 조문 → 사실관계 → 계산/해석 → 결론 4단계로 답을 작성하세요. "
            "(조문 번호는 실제 존재하는 것만 사용)"
        ),
        model_alias="nemotron",
    )
)

dd = DataDesigner(model_providers=[provider])

print(f"=== PREVIEW: {NUM_ROWS} rows ===", flush=True)
result = dd.preview(builder, num_records=NUM_ROWS)
print(f"=== PREVIEW DONE (type={type(result).__name__}) ===", flush=True)

# result 구조 탐색
attrs = [a for a in dir(result) if not a.startswith("_")]
print("attrs:", attrs)

# 데이터 추출 시도
records = None
for candidate in ("dataset", "records", "data", "rows"):
    if hasattr(result, candidate):
        obj = getattr(result, candidate)
        try:
            records = obj.to_dict(orient="records")
            print(f"[ok] extracted via .{candidate}.to_dict()")
            break
        except AttributeError:
            pass
        if isinstance(obj, list):
            records = obj
            print(f"[ok] extracted via .{candidate} (list)")
            break

if records is None:
    print("[warn] dataset 미추출 — result repr:")
    print(repr(result)[:1000])
else:
    with OUT_PATH.open("w", encoding="utf-8") as fp:
        for r in records:
            fp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(f"=== {len(records)} rows → {OUT_PATH} ===")
    for i, r in enumerate(records, 1):
        cot = str(r.get("reasoning_cot", ""))
        print(f"[{i}] 세목={r.get('세목')} 난이도={r.get('난이도')} cot_len={len(cot)}")
        print((cot[:240] + "...") if len(cot) > 240 else cot)
        print("-" * 60)
