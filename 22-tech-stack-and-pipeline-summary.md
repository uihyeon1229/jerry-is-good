# 22 — 기술 스택 · 파이프라인 흐름 정리 (발표자용 1페이지 요약)

> 발표자가 슬라이드를 그리거나 Q&A 대응할 때 **한 장에서 스택 실사용 방법 + 파이프라인 전단계**를 확인할 수 있도록 압축.
> 상세 근거·실측 증빙은 각 링크 문서(14~21)로 연결.

---

## 1. 기술 스택 — 계획 12종 + 외부 1종 + 추가 1종 (실사용 13/14)

| # | 스택 | 실사용 방식 | 구체 파일·세션 | 실측 증빙 |
|:-:|------|-------------|----------------|-----------|
| 1 | **Brev H100 80GB SXM5** | 단일 인스턴스에서 생성·검증·학습·서빙 모두 수행 | `jerryisgood-h100-80gib-vram-sxm5`, `/ephemeral` 738GB | `artifacts/nsight/vllm_base_startup.nsys-rep` |
| 2 | **Nemotron 3 Nano 30B A3B BF16** | 학습용 base (LoRA SFT) — **FP8은 학습 불가라 BF16로 전환** | HF 캐시 `/ephemeral/cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` | 14번 §1.2 "FP8 불가 실증" |
| 2' | Nemotron 3 Nano 30B **A3B FP8** | 합성 데이터 생성·Tool-use 서빙·벤치마크 추론 | tmux `vllm_tool`, port 5000 | 19번 §3-A smoke 4/4 |
| 3 | **vLLM 0.17+ OpenAI-compatible server** | 생성 / SFT 서빙 / Tool-use / 벤치마크 — 전 세션 공통 추론 엔진 | `scripts/launch_vllm.sh`, tmux `vllm_*` | 실시간 동작 중 |
| 4 | **NeMo Data Designer** | 선언적 스키마로 1000건 자동 생성 (Sampler→LLMText→Structured→Judge→Custom) | `pipeline/builder.py` / `columns.py` / `providers.py` / `refine_loop.py` / `run_generate.py` (`from data_designer.config ...` 직접 import) | 999건 raw 생성 |
| 5 | **NeMo Curator** | 텍스트 필터 SDK 2개 직접 + dedup/KMeans CPU 대체 (cudf 미설치 환경) | `pipeline/run_curator.py` · `pipeline/curator_config.yaml` | 18번 §2, v1 999→901 |
| 6 | **NeMo Guardrails** | 2경로: ① 고속 배치(프롬프트 직접 호출) ② SDK 런타임(`LLMRails.generate_async` smoke) | `pipeline/run_guardrails.py` · `pipeline/run_guardrails_llmrails_smoke.py` · `pipeline/guardrails/config.yml` · `pipeline/guardrails_sdk/config.yml` | 15번 negative 5/5, `artifacts/nemoguardrails_llmrails_smoke.json` |
| 7 | **NeMo Framework (SFT)** | ❌ 대체 → **Unsloth 공식 Colab 레시피** | (공식 가이드 16 GPU 요구, 우리는 1장) | 14번 §2 |
| 8 | **NVIDIA Build API** | ① `llama-nemotron-embed-1b-v2` 임베딩 (Curator semantic dedup / 페르소나 클러스터) ② `llama-3.3-nemotron-super-49b` 원격 Nemotron (교차 검증·Guardrails LLM) | `pipeline/embed_nvidia.py` · `pipeline/validators/build_api_cross.py` · `pipeline/run_guardrails.py --base-url` | 전 파이프라인에서 사용 |
| 9 | **Nsight Systems** | vLLM 30B BF16 로드+서빙 120초 트레이스 캡처 | `nsys profile --trace=cuda,nvtx,osrt --duration=120` → `artifacts/nsight/vllm_base_startup.nsys-rep` (15 MB) | git origin 반영 |
| 10 | **Nemotron-Personas-Korea** | 100만명 중 10K 샘플 → k-means (NVIDIA embed) → **k=200 대표 페르소나**로 질문 다양성 확보 | `pipeline/personas.py` · `pipeline/fetch_personas.py` · `scripts/cluster_personas.py` | 문서 12 §7-2 |
| 11 | **NVIDIA NIM** | Build API의 내부 백엔드로 간접 사용 | (Build API 호출 시 자동) | 발표 문구용 |
| 12 | **NeMo Evaluator** | `score_judge.py` 결과를 공식 `EvaluationResult` 스키마로 wrap | `benchmark/nemo_evaluator_wrap.py` → `benchmark/nemo_evaluator_result.json` (tasks: `korean_law_cot_before/after`) | git origin 반영 |
| 13 | **cuML** | ❌ 대체 → `sklearn.cluster.KMeans` CPU (Curator cluster_balance) | (RAPIDS 미설치, 스케일상 CPU로 충분) | 18번 §4 |
| +α | **Korean Law MCP** | L2 `verify_citations` (결정론 조문 검증) / Tool-use `search_law + get_law_text` | `pipeline/validators/citation_validator.py` · `demo/nemotron_tool_call.py` · `demo/app_toolcall.py` · https://korean-law-mcp.fly.dev | 15번 negative 5/5, 19번 Tool-use 4/4 |
| +β | **Unsloth** (미계획·추가) | Nemotron 3 Nano 30B A3B 공식 Colab 레시피 — 단일 H100 1장 LoRA SFT | `training/sft_unsloth.py` · `/ephemeral/venvs/unsloth` · `mamba_ssm==2.2.5 + causal_conv1d==1.5.2` | 14번 전체, SFT loss 0.395 수렴 |

**요약 숫자**: 계획 12종 중 **실사용 10 + 대체 2**, 추가 도입 2(MCP·Unsloth) → **실사용 14종**.

---

## 2. 파이프라인 전체 흐름 — 데이터 생성 → 검증 → 학습 → 평가

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        원본 자산 & 시드 (S0)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Nemotron-Personas-Korea 10K  ─┬─►  NVIDIA embed 1B  ─►  k-means(200)   │
│                                 │                         = 대표 200 페르소나 │
│  Korean Law MCP (법제처 DB) ────┘                                         │
│  세목 가이드 (세법·민법·노동법 8종) + 질문유형(5) + 난이도(3)                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S1 · L1 raw 생성  —  NeMo Data Designer (pipeline/run_generate.py)       │
│     • Sampler: 페르소나×세목×유형×난이도                                     │
│     • custom column seed_context: 해당 세목 조문 추출 (MCP + 화이트리스트)   │
│     • llm-text question: Nemotron 3 Nano FP8 (vLLM 공유)                  │
│     • llm-text reasoning_cot: Nemotron 3 Nano FP8 (4단계 CoT 강제)        │
│     • llm-structured metadata: applied_law_mst 등 Pydantic schema         │
│     • llm-judge quality_score: legal_accuracy / cot_depth / practical_utility │
│  → output/raw/tax_cot_v3_1000.jsonl (999 rows)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S2 · L2 조문 실존 검증  —  Korean Law MCP verify_citations (L2)           │
│     • pipeline/run_verify_citations.py                                    │
│     • cited_laws_valid_ratio, has_hallucination, invalid_refs 부여         │
│  → output/verified/tax_cot_v3_1000_verified.jsonl                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S3 · A1 부분 refine  —  저품질 샘플만 재생성                              │
│     • pipeline/run_partial_refine.py                                      │
│     • valid_ratio<0.7인 세목만 Nemotron으로 재생성 (평균 1.3회/record)      │
│  → output/refined/tax_cot_v3_1000_partial.jsonl (999)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S3.5 · B1 교차 검증  —  Build API Super 49B (원격 Nemotron)                │
│     • pipeline/validators/build_api_cross.py                              │
│     • cross_overlap (Jaccard)로 독립 평가자 지표 확보                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S5 · NeMo Curator 8단계  (pipeline/run_curator.py, 11분)                  │
│     1 exact_dedup        (sha256)           999 → 999                    │
│     2 fuzzy_dedup        (datasketch MinHash) 999 → 999                  │
│     3 semantic_dedup     (NVIDIA embed+cosine) 999 → 998                 │
│     4 length_filter      (NeMo Curator WordCountFilter)  998 → 997       │
│     5 language_filter    (한국어 휴리스틱) 997 → 996                       │
│     6 citation_threshold (valid_ratio≥0.5) 996 → 985                     │
│     7 judge_threshold    (cot_depth.score≥3) 985 → 901                   │
│     8 cluster_balance    (sklearn KMeans)   901 → 901 (스킵, 이미 균형)   │
│  → output/curated/tax_cot_v3_curated.jsonl (901)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S4 · NeMo Guardrails  (pipeline/run_guardrails.py, 40초)                 │
│     • Tier-1 Regex: PII/탈세키워드/자격사칭 즉시 차단                       │
│     • Tier-2 LLM self_check_output: Nemotron Super 49B로 YES/NO 판정      │
│     (SDK 런타임은 pipeline/run_guardrails_llmrails_smoke.py 로 별도 증빙)   │
│  → output/safe/tax_cot_v3_safe.jsonl (901 → 901, 전수 통과)                │
│  ★ 의도적 위반 negative set 5건 → 5/5 정답 (문서 15)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S6 · Finalize  (pipeline/run_finalize_train.py)                          │
│     • ChatML 변환: system / user / assistant                               │
│     • 빈 CoT·환각 제거, eval 5% 분리                                       │
│  → output/final/train.jsonl (803) + eval.jsonl (42) + filter_stats.json   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S7 · SFT (Unsloth)  —  training/sft_unsloth.py                           │
│     • base: NVIDIA-Nemotron-3-Nano-30B-A3B-**BF16**  (FP8 불가)           │
│     • LoRA r=16 α=32 dropout=0, target q/k/v/o/gate/up/down_proj + **in_proj/out_proj** (Mamba) │
│     • scripts/launch_sft_chain.sh: Phase1 500×1ep (dry-run) → Phase2 803×3ep │
│     • loss 226 → 0.395 (FP8→BF16+Unsloth 600× 개선, 총 66분)              │
│  → /ephemeral/training_checkpoints/tax_cot_lora_v2/final  + 2단 백업       │
│                                                                            │
│  (부록 ablation) Qwen 2.5-1.5B + 동일 803건 × 3ep = 132초                   │
│  → /ephemeral/training_checkpoints/qwen15b_tax_lora/final                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S8 · 벤치마크  (benchmark/)                                               │
│     • run_generate.py — base/FT 각각 20문제 답변 수집                       │
│     • score_judge.py   — expected_laws cov / cross_overlap / L2 (4축)     │
│     • score_qualitative.py — 면책 고지 / 거절 신호 / CoT 준수 / 인용 밀도    │
│     • extract_diff_samples.py — Top-K Before/After diff                    │
│     • nemo_evaluator_wrap.py — NeMo Evaluator 스키마 래핑                   │
│  → report.md · report_qualitative.md · sample_diffs.md · nemo_evaluator_result.json │
│                                                                            │
│  실측 핵심 수치:                                                           │
│     Nemotron 30B  : 면책 고지 65→90% (+25pp), 거절 신호 ×3                │
│     Qwen 1.5B     : 면책 0→100% (+100pp), expected_laws +27%, 환각 -5pp    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  S9 · 라이브 데모 (demo/)                                                   │
│     Demo-1 : 파이프라인 샘플 1건 생성 로그 (CLI)                             │
│     Demo-2 : **Tool-use 라이브** — Nemotron + Korean Law MCP 실시간 조회    │
│              (demo/nemotron_tool_call.py / app_toolcall.py, 문서 19)       │
│     Demo-3 : **Base vs Fine-tuned 나란히 비교**                             │
│              (demo/app_compare.py, Nemotron 30B or Qwen 1.5B 둘 다 지원)    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 데이터 흐름 요약 (건수 퍼넬)

```
10,000 페르소나  ──►  200 대표 페르소나  ──►  1,000 seed 조합
                                                 │
                                                 ▼
                        L1 생성 Nemotron      999 raw
                        L2 MCP 검증           999 verified
                        A1 부분 refine        999 refined
                                                 │
                                                 ▼
            Curator 8단계                   999 → 901
            Guardrails 2-tier               901 → 901
            Finalize                        901 → 803 train / 42 eval
                                                 │
                                                 ▼
            SFT (Unsloth, 30B BF16)          803 × 3ep = 9 sample exposures / row
                                                 │
                                                 ▼
            20문제 벤치마크 (외부 질문)      정성·정량 리포트
```

---

## 3. 발표 슬라이드에 그대로 쓸 수 있는 수치 5종

| # | 수치 | 출처 | 해커톤 가치 |
|:-:|------|------|-------------|
| 1 | **Guardrails negative 5/5 (100%)** | 문서 15 | 안전성 양방향 실증 |
| 2 | **SFT loss 226 → 0.395 (600× 개선)** | 문서 14 | FP8→BF16+Unsloth 기술 성취 |
| 3 | **SFT 속도 110s → 13s/step (8.5×)** | 문서 14 | Unsloth 효과 |
| 4 | **Qwen 1.5B 면책 0→100% (+100pp)** | 문서 21 | 데이터 효과 실증 (변수 통제) |
| 5 | **Qwen 1.5B expected_laws +27%** | 문서 21 | 조문 커버리지 개선 |

---

## 4. 연관 문서 (빠른 이동)

| 번호 | 제목 |
|:-:|------|
| 10 | 원 계획 아키텍처 (Slide 8 다이어그램) |
| 11 | 파이프라인 고도화 9종 (B1·C1·D1 등) |
| 12 | 발표 단일 소스 (슬라이드 타이머·내레이션) |
| 13 | 합성 데이터 대표 샘플 (PPT 복붙용) |
| 14 | SFT 스택 교체 (FP8→BF16·HF→Unsloth) |
| 15 | Guardrails Negative Validation 5/5 |
| 16 | Base vs FT 데모 설계 |
| 17 | Nemotron 30B 벤치마크 리포트 |
| 18 | 스택 실구현 vs 계획 매핑 (Q&A 방어) |
| 19 | L5 Tool-use 라이브 데모 가이드 + 4/4 smoke |
| 20 | 발표 경쟁력 평가 + 전략 |
| 21 | Qwen 1.5B Model Size Ablation |
| **22** | **(본 문서) 스택·파이프라인 1페이지 요약** |

---

## 5. 중요 경로 빠른 참조

**데이터**:
- 최종 학습 데이터 (ChatML, PPT 복붙용): `backup_sft_20260421_2314/train.jsonl` (803건, 로컬)
- 풍부한 메타 포함 원본: VM `output/refined/tax_cot_v3_1000_partial.jsonl` (999건 + quality_score)
- 벤치마크 결과: `benchmark/answers_*.jsonl` + `report*.md`

**어댑터** (backup):
- 30B FT: `backup_sft_phase2_20260422/final_phase2.tgz` (1.6 GB, 로컬) + VM `/ephemeral/backups/sft_phase2_20260422/`
- 1.5B FT: VM `/ephemeral/training_checkpoints/qwen15b_tax_lora/final/` (74 MB)

**라이브 서비스** (현재 기동 중):
- `vllm_qwen` tmux · port 5000 · `qwen15b-base` + `qwen_tax_lora`
- `st_compare` tmux · port 8700 · Streamlit 비교 UI
- WSL port-forward 5000·8700 유지 중 (이 Claude Code 세션 생명)

**발표 중 재시작해야 할 때**:
- `scripts/launch_vllm.sh` (레거시 FP8) · `scripts/launch_sft_chain.sh` (SFT)
- 문서 19 §2.1 / 문서 20 §4.3 체크리스트 참조
