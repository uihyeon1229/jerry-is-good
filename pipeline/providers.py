"""Data Designer용 ModelProvider / ModelConfig 공통 정의."""

from __future__ import annotations

from data_designer.config import (
    ChatCompletionInferenceParams,
    ModelConfig,
    ModelProvider,
)

from .settings import settings


VLLM_PROVIDER_NAME = "local_vllm"


def vllm_provider() -> ModelProvider:
    return ModelProvider(
        name=VLLM_PROVIDER_NAME,
        endpoint=settings.vllm_base_url,
        provider_type="openai",
        api_key="not-used",
    )


def nemotron_model(
    alias: str,
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    extra_body: dict | None = None,
) -> ModelConfig:
    """역할별(alias) Nemotron ModelConfig 프리셋."""
    params = ChatCompletionInferenceParams(
        temperature=temperature,
        max_tokens=max_tokens or settings.max_tokens_cot,
        max_parallel_requests=settings.max_parallel,
    )
    if extra_body:
        params.extra_body = extra_body
    return ModelConfig(
        alias=alias,
        model=settings.vllm_model,
        provider=VLLM_PROVIDER_NAME,
        inference_parameters=params,
    )


def default_model_configs() -> list[ModelConfig]:
    """파이프라인이 쓰는 4가지 역할별 모델 프리셋 (alias 이름이 컬럼에서 참조됨)."""
    return [
        nemotron_model(
            "question_gen",
            temperature=0.9,
            max_tokens=settings.max_tokens_question,
        ),
        nemotron_model(
            "cot_gen",
            temperature=0.7,
            max_tokens=settings.max_tokens_cot,
        ),
        nemotron_model(
            "structured",
            temperature=0.1,
            max_tokens=settings.max_tokens_metadata,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        nemotron_model(
            "judge",
            temperature=0.1,
            max_tokens=settings.max_tokens_judge,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
    ]
