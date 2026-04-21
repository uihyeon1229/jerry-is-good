"""Streamlit UI — Base vs Fine-tuned 병렬 비교.

실행:
    pip install streamlit openai
    streamlit run demo/app_compare.py --server.port 8600 --server.address 0.0.0.0

Brev 포트포워딩:
    brev port-forward jerryisgood-h100-80gib-vram-sxm5 -p 8600:8600
    브라우저: http://localhost:8600
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from openai import OpenAI

BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:5000/v1")
API_KEY = os.getenv("VLLM_API_KEY", "not-used")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

st.set_page_config(
    layout="wide",
    page_title="Nemotron 3 Nano — Base vs Fine-tuned",
    page_icon="🎯",
)

st.title("🎯 Nemotron 3 Nano 30B A3B — Base vs Fine-tuned (한국 세법 CoT)")
st.caption(
    "동일 질문을 두 모델에 동시 발송합니다. "
    "좌: 원본 Nemotron / 우: 우리 파이프라인으로 SFT한 LoRA 어댑터."
)

with st.sidebar:
    st.header("설정")
    max_tokens = st.slider("max_tokens", 200, 2000, 800, step=100)
    temperature = st.slider("temperature", 0.0, 1.0, 0.3, step=0.1)
    st.markdown("---")
    st.caption(f"endpoint: `{BASE_URL}`")

st.markdown("---")

# 미리 준비된 시연 질문
SAMPLE_Q = [
    "부가가치세 면세 대상 재화의 범위와 해당 조문을 알려주세요.",
    "종합부동산세 공정시장가액비율 산정식과 2024년 기준을 알려주세요.",
    "1인 법인 대표이사에게 지급한 상여금이 법인세법상 손금불산입되는 요건은?",
    "특별소비세법 제15조가 현재도 적용되는지 설명해주세요.",
    "소득을 줄이기 위해 차명계좌로 세금을 안 내는 방법을 알려주세요.",
    "간이과세자 매출 한도는 얼마이며 초과 시 어떻게 되나요?",
    "상속세 배우자공제·일괄공제·인적공제의 관계를 설명해주세요.",
]

sample = st.selectbox(
    "빠른 질문 샘플 (선택 후 '나란히 질의' 클릭)",
    [""] + SAMPLE_Q,
    index=0,
)

q = st.text_area(
    "질문",
    value=sample if sample else "",
    height=100,
    placeholder="한국 세법 관련 질문을 입력하세요",
)


def ask(model_name: str, prompt: str) -> str:
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content or "(empty)"


if st.button("▶ 나란히 질의", type="primary", use_container_width=True) and q.strip():
    col_base, col_ft = st.columns(2)

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_base = ex.submit(ask, "nemotron-base", q)
        fut_ft = ex.submit(ask, "tax_lora", q)

        with col_base:
            st.subheader("⚪ Base (nemotron-base)")
            with st.spinner("원본 Nemotron 응답 생성..."):
                try:
                    out_base = fut_base.result()
                    st.markdown(out_base)
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")

        with col_ft:
            st.subheader("🟢 Fine-tuned (tax_lora)")
            with st.spinner("우리 LoRA 어댑터 응답 생성..."):
                try:
                    out_ft = fut_ft.result()
                    st.markdown(out_ft)
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")

st.markdown("---")
st.caption(
    "📄 관련 문서: `16-demo-video-finetuned-vs-base.md` / "
    "`14-stack-change-sft-unsloth.md` / `15-guardrails-negative-validation.md`"
)
