"""Nemotron 3 Nano 30B A3B FP8 + LoRA SFT 학습.

transformers + peft + trl.SFTTrainer 기반.
Nemotron FP8은 bitsandbytes 없이 그대로 로드 가능 (vLLM에서 이미 확인).

사용:
    HF_HOME=/home/shadeform/.cache/huggingface \
    TRAIN_INPUT=output/refined/tax_cot_v3.jsonl \
    python training/sft_nemotron_nano_lora.py

중요: vLLM이 port 5000에서 GPU 31GB 점유 중이면 OOM.
       SFT 전에 `tmux kill-session -t vllm` 필요.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)
from trl import SFTConfig, SFTTrainer

# --- 환경 설정 ---------------------------------------------------------------
MODEL_NAME = os.getenv(
    "SFT_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8"
)
TRAIN_INPUT = Path(
    os.getenv("TRAIN_INPUT", "output/refined/tax_cot_v3_refined.jsonl")
)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "training/checkpoints/tax_cot_lora"))
LOG_DIR = Path(os.getenv("LOG_DIR", "training/logs"))

# 하이퍼파라미터
LORA_R = int(os.getenv("LORA_R", "16"))
LORA_ALPHA = int(os.getenv("LORA_ALPHA", "32"))
LORA_DROPOUT = float(os.getenv("LORA_DROPOUT", "0.05"))
NUM_EPOCHS = int(os.getenv("NUM_EPOCHS", "3"))
LEARNING_RATE = float(os.getenv("LR", "1e-5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1"))
GRAD_ACCUM = int(os.getenv("GRAD_ACCUM", "16"))
MAX_SEQ_LEN = int(os.getenv("MAX_SEQ_LEN", "4096"))
MIN_COT_LEN = int(os.getenv("MIN_COT_LEN", "300"))

# Chain 실행 지원
SFT_MAX_SAMPLES = int(os.getenv("SFT_MAX_SAMPLES", "0"))  # 0 = 전량
SFT_RESUME = os.getenv("SFT_RESUME", "0") == "1"
SFT_SEED = int(os.getenv("SFT_SEED", "42"))

SYSTEM_PROMPT = (
    "당신은 한국 법률 전문가입니다. 질문에 대해 적용 조문 → 사실관계 → 해석/계산 → 결론 "
    "4단계로 답하세요. 조문은 실제 존재하는 것만 인용하세요."
)


def load_train_data(path: Path) -> list[dict]:
    """필터 + ChatML 구성."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        question = (r.get("question") or "").strip()
        cot = (r.get("reasoning_cot") or "").strip()
        if len(cot) < MIN_COT_LEN:
            continue
        if r.get("has_hallucination") is True:
            continue
        if (r.get("cited_laws_valid_ratio") or 0) < 0.5:
            continue
        records.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": cot},
                ]
            }
        )
    return records


def main() -> None:
    print(f"=== SFT LoRA 학습 시작 ===", flush=True)
    print(f"model:  {MODEL_NAME}", flush=True)
    print(f"input:  {TRAIN_INPUT}", flush=True)
    print(f"output: {OUTPUT_DIR}", flush=True)

    # 1. 데이터 로드
    data = load_train_data(TRAIN_INPUT)
    print(f"=== 로드된 학습 데이터(필터 통과): {len(data)}건 ===", flush=True)

    # dry-run 모드: 상위 N건만 사용
    if SFT_MAX_SAMPLES > 0:
        data = data[:SFT_MAX_SAMPLES]
        print(f"=== SFT_MAX_SAMPLES={SFT_MAX_SAMPLES} 적용 → 학습 데이터 {len(data)}건 ===", flush=True)

    if len(data) < 100:
        print("⚠ 데이터가 너무 적음 (< 100). 그래도 계속 진행합니다.", flush=True)

    ds = Dataset.from_list(data)
    split = ds.train_test_split(test_size=0.05, seed=SFT_SEED)
    train_ds, eval_ds = split["train"], split["test"]
    print(f"  train={len(train_ds)}, eval={len(eval_ds)}", flush=True)

    # 2. 모델·토크나이저
    print("=== 모델 로드 중 (~1분) ===", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # 3. LoRA
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. 학습 설정
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    sft_cfg = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_dir=str(LOG_DIR),
        logging_steps=5,
        save_steps=50,
        save_total_limit=3,
        eval_strategy="steps",
        eval_steps=50,
        max_length=MAX_SEQ_LEN,
        packing=False,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )

    print(f"=== 학습 시작 (resume={SFT_RESUME}) ===", flush=True)
    if SFT_RESUME and OUTPUT_DIR.exists():
        # checkpoint-XXX 폴더 존재하는지 확인
        ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*"))
        if ckpts:
            print(f"=== resuming from {ckpts[-1]} ===", flush=True)
            trainer.train(resume_from_checkpoint=True)
        else:
            print("=== SFT_RESUME=1 이지만 checkpoint 없음 → 처음부터 학습 ===", flush=True)
            trainer.train()
    else:
        trainer.train()

    # 5. 최종 어댑터 저장
    final_dir = OUTPUT_DIR / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"=== DONE → {final_dir} ===")


if __name__ == "__main__":
    main()
