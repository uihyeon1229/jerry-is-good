"""nano_v3 reasoning-parser 분리 동작 확인 (thinking/content 2필드)."""

import os
from openai import OpenAI

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
MODEL_NAME = os.getenv("VLLM_MODEL", "nemotron")

client = OpenAI(base_url=BASE_URL, api_key="not-used")

resp = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {
            "role": "system",
            "content": (
                "당신은 한국 세법 CoT 전문가입니다. "
                "적용 조문을 인용하며 단계별로 추론해 답하세요."
            ),
        },
        {
            "role": "user",
            "content": (
                "연봉 8,000만원인 근로자의 근로소득공제액은 얼마인가? "
                "소득세법 제47조를 인용해 계산 과정을 단계별로 보여주세요."
            ),
        },
    ],
    temperature=0.3,
    max_tokens=1024,
    extra_body={"chat_template_kwargs": {"enable_thinking": True}},
)

msg = resp.choices[0].message
print("=== reasoning_content (thinking) ===")
print(getattr(msg, "reasoning_content", "<<no reasoning_content field>>"))
print()
print("=== content (final answer) ===")
print(msg.content)
print()
print("=== usage ===")
print(resp.usage)
