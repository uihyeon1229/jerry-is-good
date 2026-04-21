"""Unsloth 기반 Nemotron-3-Nano-30B-A3B-BF16 LoRA SFT.

Unsloth 공식 notebook (Nemotron-3-Nano-30B-A3B_A100.ipynb) 레시피를 그대로 반영.
  - target_modules: q/k/v/o/gate/up/down_proj + in_proj/out_proj (Mamba mixer)
  - LR 2e-4, adamw_8bit, linear scheduler
  - train_on_responses_only (assistant 응답만 loss)
  - attn_implementation="eager", gradient_checkpointing="unsloth"

실행:
  source /ephemeral/venvs/unsloth/bin/activate
  TRAIN_INPUT=output/final/train.jsonl \
  NUM_EPOCHS=1 SFT_MAX_SAMPLES=500 \
  python training/sft_unsloth.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only  # noqa: E402

import torch  # noqa: E402
from datasets import Dataset  # noqa: E402
from trl import SFTConfig, SFTTrainer  # noqa: E402


# --- 환경 설정 ---------------------------------------------------------------
MODEL_NAME = os.getenv(
    "SFT_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
)
TRAIN_INPUT = Path(os.getenv("TRAIN_INPUT", "output/final/train.jsonl"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "training/checkpoints/tax_cot_lora_v2"))
LOG_DIR = Path(os.getenv("LOG_DIR", "training/logs"))

LORA_R = int(os.getenv("LORA_R", "16"))
LORA_ALPHA = int(os.getenv("LORA_ALPHA", "32"))
LORA_DROPOUT = float(os.getenv("LORA_DROPOUT", "0"))
MAX_SEQ_LEN = int(os.getenv("MAX_SEQ_LEN", "2048"))

NUM_EPOCHS = int(os.getenv("NUM_EPOCHS", "1"))
SFT_MAX_SAMPLES = int(os.getenv("SFT_MAX_SAMPLES", "0"))  # 0=전량
SFT_RESUME = os.getenv("SFT_RESUME", "0") == "1"
LEARNING_RATE = float(os.getenv("LR", "2e-4"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4"))
GRAD_ACCUM = int(os.getenv("GRAD_ACCUM", "2"))
WARMUP_STEPS = int(os.getenv("WARMUP_STEPS", "5"))
SEED = int(os.getenv("SFT_SEED", "3407"))

SYSTEM_PROMPT = (
    "당신은 한국 법률 전문가입니다. 질문에 대해 적용 조문 → 사실관계 → 해석/계산 → 결론 "
    "4단계로 답하세요. 조문은 실제 존재하는 것만 인용하세요."
)

MIN_COT_LEN = int(os.getenv("MIN_COT_LEN", "300"))


def load_train_data(path: Path) -> list[dict]:
    """ChatML(신) / legacy(구) 모두 지원."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)

        msgs = r.get("messages")
        if isinstance(msgs, list) and msgs:
            assistant = next((m for m in msgs if m.get("role") == "assistant"), None)
            if not assistant or len((assistant.get("content") or "").strip()) < MIN_COT_LEN:
                continue
            records.append({"messages": msgs})
            continue

        q = (r.get("question") or "").strip()
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
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": cot},
                ]
            }
        )
    return records


def main() -> None:
    print("=== SFT (Unsloth) 시작 ===", flush=True)
    print(f"model:  {MODEL_NAME}", flush=True)
    print(f"input:  {TRAIN_INPUT}", flush=True)
    print(f"output: {OUTPUT_DIR}", flush=True)
    print(
        f"epochs={NUM_EPOCHS} max_samples={SFT_MAX_SAMPLES} lr={LEARNING_RATE} "
        f"bs={BATCH_SIZE} ga={GRAD_ACCUM}",
        flush=True,
    )

    # 1. 데이터
    data = load_train_data(TRAIN_INPUT)
    print(f"=== 필터 통과: {len(data)}건 ===", flush=True)
    if SFT_MAX_SAMPLES > 0:
        data = data[:SFT_MAX_SAMPLES]
        print(f"=== MAX_SAMPLES={SFT_MAX_SAMPLES} → {len(data)}건 ===", flush=True)

    ds = Dataset.from_list(data)

    # 2. 모델 로드 (Unsloth)
    print("=== 모델 로드 (Unsloth) ===", flush=True)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=False,
        load_in_8bit=False,
        full_finetuning=False,
        trust_remote_code=True,
        unsloth_force_compile=True,
        attn_implementation="eager",
    )

    # 3. LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
            "in_proj", "out_proj",   # Mamba mixer projections
        ],
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
        use_rslora=False,
        loftq_config=None,
    )

    # 4. dataset → text (chat template 적용)
    def _format(ex):
        return {
            "text": tokenizer.apply_chat_template(
                ex["messages"], tokenize=False, add_generation_prompt=False
            )
        }

    ds = ds.map(_format)

    # 5. Trainer
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        eval_dataset=None,
        args=SFTConfig(
            output_dir=str(OUTPUT_DIR),
            dataset_text_field="text",
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.001,
            lr_scheduler_type="linear",
            seed=SEED,
            report_to="none",
            save_steps=50,
            save_total_limit=3,
            max_seq_length=MAX_SEQ_LEN,
        ),
    )

    # 6. 응답만 학습
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    # 7. 학습
    print("=== 학습 시작 ===", flush=True)
    gpu_stats = torch.cuda.get_device_properties(0)
    max_memory = round(gpu_stats.total_memory / 1024**3, 2)
    print(f"GPU: {gpu_stats.name}, total={max_memory} GB", flush=True)

    if SFT_RESUME and OUTPUT_DIR.exists():
        ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*"))
        if ckpts:
            print(f"=== resume from {ckpts[-1]} ===", flush=True)
            trainer.train(resume_from_checkpoint=True)
        else:
            print("=== RESUME=1 이지만 ckpt 없음 → 처음부터 ===", flush=True)
            trainer.train()
    else:
        trainer.train()

    # 8. 저장
    final_dir = OUTPUT_DIR / "final"
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"=== DONE → {final_dir} ===", flush=True)


if __name__ == "__main__":
    main()
