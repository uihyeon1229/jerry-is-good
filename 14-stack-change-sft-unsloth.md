# 14 — SFT 스택 변경 (Nemotron 3 Nano 30B LoRA SFT: HF PEFT → Unsloth)

> **작성 시점**: 2026-04-22 새벽, Day1 밤 SFT 실패 복구 과정에서 확정
> **대상 독자**: 본 해커톤을 이어받을 다른 트랙/팀 개발자
> **단일 문장 요약**: **FP8 모델은 LoRA SFT 불가능**하므로 `-BF16`로 교체하고, HF `transformers+peft+trl` 대신 **Unsloth 공식 레시피**를 그대로 채용한다.

---

## 1. 왜 바꿨나 — Day1 Phase 1 실패 보고

### 증상
- Nemotron 3 Nano 30B A3B **FP8** 원본 + HF `transformers + peft.LoraConfig + trl.SFTTrainer` 조합으로 1차 학습.
- 30 step 내내 **loss 242 → 226** 거의 불변, `mean_token_accuracy = 0.012 (1.2%)`.
- 학습은 "완료"되지만 gradient가 의미 있게 흐르지 않음.

### 근본 원인 (5가지 모두 기여, 1·2번이 치명적)

| # | 요소 | 우리 (잘못) | 정답 | 영향도 |
|---|------|------------|------|--------|
| 1 | **체크포인트 dtype** | `...-FP8` | `...-BF16` | 🔴 **치명** |
| 2 | **LoRA target_modules** | q/k/v/o + gate/up/down_proj | 위 + **in_proj, out_proj** (Mamba mixer projection) | 🔴 치명 |
| 3 | **attn_implementation** | 기본값 (SDPA) | `"eager"` | 🟠 큼 |
| 4 | **learning_rate** | 1e-5 | 2e-4 (20×) | 🟠 큼 |
| 5 | **학습 대상 토큰** | 전체 시퀀스 | **assistant 응답만** (`train_on_responses_only`) | 🟡 중 |
| 6 | `prepare_model_for_kbit_training` 호출 | 호출함 | **호출 안 함** (Unsloth가 내부 처리) | 🟡 중 |
| 7 | lr_scheduler | cosine | linear | 🟢 작음 |
| 8 | optim | 기본 (adamw_torch) | `adamw_8bit` (bitsandbytes) | 🟢 작음 |

### FP8로는 왜 아예 불가능한가
- PyTorch의 FP8 dtype은 **forward 연산 최적화** 중심. 표준화된 backward 경로 없음.
- LoRA는 base weight의 gradient를 받아 low-rank matrix를 업데이트해야 하는데, FP8 weight에서 흘러나오는 gradient가 numerical 노이즈 수준.
- NVIDIA 모델카드에도 `-FP8`/`-NVFP4` variant는 **vLLM / TensorRT-LLM serving 전용**으로 명시. training은 `-BF16` / `-Base-BF16`을 사용하라고 되어 있음.
- Unsloth 공식 지원도 bf16/fp16 원본 + 선택적 4/8bit bitsandbytes 양자화. FP8은 미지원.
- ✅ **표준 워크플로우**: Train on BF16 → (옵션) LoRA 병합 → FP8 재양자화 → vLLM serving.

---

## 2. 새 스택 (확정본)

### 2.1 모델
- **Training base**: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` (≈ 60 GB on disk, single H100 80GB LoRA는 ~60 GB VRAM).
- **Serving base** (SFT 후): `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` (vLLM, 31 GB) + LoRA 어댑터를 merge_and_unload 후 FP8 재양자화, 또는 LoRA 직접 로딩.

### 2.2 Python / CUDA 스택
> **주의**: 기존 프로젝트 venv(`/home/shadeform/track3`, Curator/Guardrails/Cross-verify용)와 **분리된 새 venv**를 만든다. Unsloth는 `torch==2.7.1` 고정 요구, 기존 env는 `torch 2.10+cu128`을 사용 중이라 섞을 수 없다.

```bash
# VM ephemeral(대용량) 디스크에 생성 — OS 디스크는 이미 포화
python3 -m venv /ephemeral/venvs/unsloth
source /ephemeral/venvs/unsloth/bin/activate

# core stack
TMPDIR=/ephemeral/tmp PIP_CACHE_DIR=/ephemeral/cache/pip \
uv pip install \
    "torch==2.7.1" "triton>=3.3.0" numpy pillow torchvision bitsandbytes \
    "transformers==4.56.2" "trl==0.22.2" \
    "unsloth_zoo @ git+https://github.com/unslothai/unsloth-zoo" \
    "unsloth @ git+https://github.com/unslothai/unsloth" \
    datasets accelerate peft pyyaml

# Mamba extensions (반드시 --no-build-isolation: 빌드 환경이 엉뚱한 torch를 끌어오지 않도록)
TMPDIR=/ephemeral/tmp PIP_CACHE_DIR=/ephemeral/cache/pip \
pip install --no-build-isolation "mamba_ssm==2.2.5" "causal_conv1d==1.5.2"
```

### 2.3 LoRA 설정 (Unsloth 공식 notebook 그대로)

```python
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from trl import SFTTrainer, SFTConfig

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
    max_seq_length = 2048,
    load_in_4bit = False,
    load_in_8bit = False,
    full_finetuning = False,
    trust_remote_code = True,
    unsloth_force_compile = True,
    attn_implementation = "eager",          # ← 필수
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
        "in_proj", "out_proj",              # ← Mamba mixer projections (필수)
    ],
    lora_alpha = 32,
    lora_dropout = 0,                       # ← 0 권장
    bias = "none",
    use_gradient_checkpointing = "unsloth", # ← 30% VRAM 절감, 2x batch
    random_state = 3407,
    use_rslora = False,
    loftq_config = None,
)

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = ds,
    args = SFTConfig(
        dataset_text_field = "text",
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 2,
        warmup_steps = 5,
        num_train_epochs = 1,
        learning_rate = 2e-4,               # ← LoRA 표준 (기존 1e-5 20배 낮았음)
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.001,
        lr_scheduler_type = "linear",
        seed = 3407,
        report_to = "none",
    ),
)

trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\n",
    response_part    = "<|im_start|>assistant\n",
)
```

### 2.4 MoE 특화 주의사항
- **Router layer는 fine-tune 대상 제외** — Unsloth가 기본적으로 MoE router를 PEFT 대상에서 배제함. 수동 target에 넣지 말 것.
- **Reasoning 보존**: 공식 가이드 상 "reasoning 75% : non-reasoning 25%" 비율 권장. 우리 합성 데이터는 100% CoT라 더 안전.

---

## 3. 파일 변경 목록 (레포 기준)

| 파일 | 변경 |
|------|------|
| `training/sft_unsloth.py` | **신규 작성** (Unsloth 레시피 적용한 SFT 진입점) |
| `training/sft_nemotron_nano_lora.py` | **비권장** (레거시, 학습 실패). 스토리용 보존 가능하나 실행은 `sft_unsloth.py` 사용 |
| `scripts/launch_sft_chain.sh` | `SFT_MODEL=...-BF16`, `LR=2e-4`로 환경변수 주입. Python 괄호 버그(62줄) 수정됨 |
| `14-stack-change-sft-unsloth.md` | 본 문서 |

### 기존 데이터 자산은 그대로 사용
- `output/refined/tax_cot_v3_1000_partial.jsonl` (999건 raw)
- `output/curated/tax_cot_v3_curated.jsonl` (901건, 8단계 NeMo Curator 통과)
- `output/safe/tax_cot_v3_safe.jsonl` (901건, NeMo Guardrails 통과)
- `output/final/train.jsonl` (**803건 ChatML** — SFT 입력)
- `output/final/eval.jsonl` (42건)

SFT 프레임워크만 교체되며 **데이터 파이프라인 재실행은 불필요**.

---

## 4. 발표 메시지 업데이트 (12-presentation-final.md 연동)

> **변경 후 메시지**
>
> "우리는 단일 H100 80GB에서 Nemotron 3 Nano 30B A3B BF16을 Unsloth 공식 레시피로 LoRA SFT 하여 한국 법률 CoT 도메인 어댑터를 생성했다. FP8 checkpoint는 학습용이 아닌 serving용임을 실측(loss 242→226 실패)으로 확인하고 BF16으로 전환, Mamba hybrid 아키텍처에 맞춰 `in_proj/out_proj`를 LoRA target에 포함시키고 `train_on_responses_only`로 assistant 토큰만 학습했다."

### Q&A 대비
- **"FP8이 Nemotron의 차별점 아닌가?"** → FP8은 **serving 효율** 차별점. training은 BF16 → LoRA 후 FP8 재양자화하여 serving. 우리가 직접 이 실험을 돌려 데이터로 증명함 (loss plot 첨부 가능).
- **"왜 Megatron-Bridge를 안 썼나?"** → 공식 레시피는 16 GPU(2×H100 노드) 요구. 우리는 1장 H100. Unsloth는 동일 H100 1장에서 LoRA SFT 를 공식 지원함 (A100 80GB Colab notebook 공개).
- **"왜 HF PEFT 를 버렸나?"** → Mamba hybrid + MoE에 대한 target_modules / gradient path 검증이 제한적. Unsloth는 공식 검증된 대안.

---

## 5. 인수인계 체크리스트

- [ ] 새 venv 생성 (위 2.2 명령)
- [ ] `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` 다운로드 (약 60 GB)
- [ ] `output/final/train.jsonl` 존재 확인 (803 rows)
- [ ] `python training/sft_unsloth.py` dry-run (`SFT_MAX_SAMPLES=500 NUM_EPOCHS=1`) → loss < 3.0 확인
- [ ] 풀 학습 (`NUM_EPOCHS=3 SFT_MAX_SAMPLES=0 SFT_RESUME=1`)
- [ ] 학습된 어댑터 vLLM 서빙 경로 검증

---

## 6. 레퍼런스 링크

- [Unsloth Nemotron-3 공식 가이드](https://unsloth.ai/docs/models/nemotron-3)
- [Unsloth Nemotron-3-Nano-30B-A3B_A100.ipynb (Colab)](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Nemotron-3-Nano-30B-A3B_A100.ipynb)
- [`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` HF](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16)
- [Nemotron 3 Nano 공식 SFT docs (Megatron-Bridge)](https://docs.nvidia.com/nemotron/nightly/nemotron/nano3/sft.html)
- [Unsloth 이슈 #3810 — Nemotron 3 Nano LoRA 토론](https://github.com/unslothai/unsloth/discussions/3810)
