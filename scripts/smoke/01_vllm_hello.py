"""vLLM Nemotron 서버 기본 동작 확인 (최소 호출)."""

import os
from openai import OpenAI

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
MODEL_NAME = os.getenv("VLLM_MODEL", "nemotron")

client = OpenAI(base_url=BASE_URL, api_key="not-used")

resp = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": "당신은 한국 세법 전문가입니다."},
        {"role": "user", "content": "소득세법 제20조(근로소득)의 핵심 내용을 한 문장으로 요약해 주세요."},
    ],
    temperature=0.3,
    max_tokens=256,
)

msg = resp.choices[0].message
print("=== content ===")
print(msg.content)
print()
print("=== usage ===")
print(resp.usage)
