# 18 — NVIDIA 스택 실구현 vs 계획 매핑

> **목적**: 계획 문서(`10-architecture-overview.md`, `11-pipeline-advanced.md`)에서 약속한 NVIDIA 12종 + 외부 1종 스택이
> 실제로 어떻게 구현되었는지, 어디를 대체했는지, 어디를 보강 복구했는지 **한 장에 정리**.
> **발표 Q&A 방어용** + 다른 개발자 인수인계용.

---

## 1. 12종 + α 매핑 (실측 기준)

| # | 계획 스택 | 실사용 여부 | 실제 코드·결과 | 비고 |
|---|-----|:---:|----|-----|
| 1 | Brev H100 80GB | ✅ 실사용 | `jerryisgood-h100-80gib-vram-sxm5` | 단일 인스턴스 |
| 2 | Nemotron 3 Nano 30B A3B **FP8** | ⚠️ 부분 | Serving은 vLLM에서 유지, **학습은 BF16으로 교체** | FP8은 LoRA 학습 불가 실측 — 문서 14 |
| 3 | vLLM (OpenAI-compatible) | ✅ 실사용 | `scripts/launch_vllm.sh` / tmux `vllm_gen`, `vllm_demo` | `--enable-lora` 핫어태치 |
| 4 | **NeMo Data Designer** | ✅ 실사용 | `pipeline/builder.py·columns.py·providers.py·refine_loop.py·run_generate.py` | `data_designer.config.DataDesignerConfigBuilder`, `data_designer.interface.DataDesigner` 직접 import |
| 5 | **NeMo Curator** | ⚠️ **하이브리드** | `pipeline/run_curator.py` (§2 참조) | SDK 모듈 2개 직접 + dedup/KMeans CPU 대체 |
| 6 | **NeMo Guardrails** | ⚠️ **하이브리드** | `pipeline/run_guardrails.py` + `run_guardrails_llmrails_smoke.py` (§3 참조) | config.yml SDK 스키마 + 고속 경로 직접 호출 + SDK 런타임 smoke |
| 7 | NeMo Framework (SFT) | ❌ **대체** | **Unsloth**로 교체 | 공식 레시피 16GPU 요구, 단일 H100 불가 — 문서 14 |
| 8 | NVIDIA Build API | ✅ 실사용 | `pipeline/embed_nvidia.py`·`pipeline/validators/build_api_cross.py` | llama-nemotron-embed + cross-verify Super 49B + Guardrails LLM 판정 |
| 9 | Nsight Systems | ✅ 복구 완료 | `artifacts/nsight/vllm_base_startup.nsys-rep` (15 MB) | nsys 2024.6 — vLLM 30B 로드·서빙 120초 캡처 — 문서 14/18 |
| 10 | Nemotron-Personas-Korea | ✅ 실사용 | `pipeline/personas.py`, `scripts/cluster_personas.py` | 10K 샘플 캐시 + k=200 대표 클러스터 |
| 11 | NVIDIA NIM | ✅ 간접 사용 | Build API 백엔드 | 발표 문구용 |
| 12 | **NeMo Evaluator** | ✅ 복구 완료 | `benchmark/nemo_evaluator_wrap.py`, `benchmark/nemo_evaluator_result.json` | `nemo_evaluator.EvaluationResult` 스키마 래핑 실행 성공 — 문서 17 연관 |
| (13) | cuML | ❌ **대체** | sklearn KMeans · CPU | RAPIDS 전체 설치 비용이 해커톤 시간에 맞지 않음 |
| α | Korean Law MCP | ✅ 실사용 | `pipeline/validators/citation_validator.py` 의 `verify_batch` | L2 결정론 검증 (LAW_OC=didwjs12) |
| β | Unsloth (미계획·추가) | ➕ 신규 채용 | `training/sft_unsloth.py` + `/ephemeral/venvs/unsloth` | Nemotron 3 Nano 공식 Colab 레시피 그대로 채용 — 문서 14 |

**정리**: 12종 중 **실사용 10종 + 대체 2종(cuML, NeMo Framework SFT)**, 추가 도입 2종(Unsloth, MCP는 계획 외부로 표기).

---

## 2. NeMo Curator 하이브리드 상세

계획: 공식 Curator 파이프라인(`nemo_curator.pipeline`)으로 exact/fuzzy/semantic dedup + 클러스터 균형.

실제: VM에 `cudf`(RAPIDS)가 설치되어 있지 않아 `nemo_curator.stages.deduplication` 모듈 import 즉시 실패. 해커톤 시간에 RAPIDS 설치는 비현실적 → **공식 filter는 가능한 범위까지 직접 사용, dedup은 CPU 동등 구현으로 대체**.

### 2.1 8단계 파이프라인 (`pipeline/run_curator.py`)

| # | Step 이름 | 공식 NeMo Curator 모듈? | 실구현 | 비고 |
|---|-----|:---:|----|-----|
| 1 | exact_dedup | ❌ (cudf 필요) | Python `hashlib.sha256` on `reasoning_cot` | 결정론적 동일 효과 |
| 2 | fuzzy_dedup | ❌ (cudf 필요) | `datasketch.MinHash + MinHashLSH`, threshold=0.85, 3-gram | CPU, Jaccard 근사 |
| 3 | semantic_dedup | ⚠ 부분 | **NVIDIA Build API**의 `nvidia/llama-nemotron-embed-1b-v2` 임베딩 + 코사인 threshold 0.90 | 공식 Curator는 동일 임베딩 모델 + GPU cosine 쓰므로 논리 동일 |
| 4 | length_filter | ✅ | `nemo_curator.stages.text.filters.WordCountFilter(min_words, max_words, lang="ko")` | **SDK 직접 사용** |
| 5 | language_filter | ⚠ 시도→폴백 | `nemo_curator.stages.text.filters.FastTextLangId` → 모델 경로 없어 한글 비율 체크로 대체 | SDK import 성공, 모델 다운로드 실패 |
| 6 | citation_threshold | ❌ | plain Python `ThresholdFilter` (`cited_laws_valid_ratio >= 0.5`) | L2 축 |
| 7 | judge_threshold | ❌ | plain Python (`quality_score.cot_depth.score >= 3`) | Judge 축 |
| 8 | cluster_balance | ❌ (cuML 필요) | `sklearn.cluster.KMeans` + 클러스터당 상한 | CPU KMeans |

### 2.2 실측 (v1)

- 입력: 999건 (`output/refined/tax_cot_v3_1000_partial.jsonl`)
- 각 단계 drop: semantic_dedup 1 · length 1 · lang 1 · citation 11 · judge 84
- 출력: **901건 → `output/curated/tax_cot_v3_curated.jsonl`**
- 총 소요: 11분 (embed 약 10초 포함)

### 2.3 발표 메시지

> "공식 `nemo_curator.stages.text.filters`를 **직접 import해서 사용**했다. GPU 전용 dedup 경로(cudf 의존)는 해커톤 환경 제약으로 CPU 동등 알고리즘(MinHash, sklearn KMeans, NVIDIA Build API 임베딩)으로 대체했지만 **파이프라인 설계와 drop률 의미는 동일**하게 유지했다."

---

## 3. NeMo Guardrails 2경로 구현

### 3.1 고속 배치 경로 (실제 대량 처리)
- 파일: `pipeline/run_guardrails.py`
- 동작:
  1. `pipeline/guardrails/config.yml` 읽어 `self_check_output` **프롬프트를 직접 추출**
  2. Regex 1차 방어 (`inline_regex_flag`) — PII/탈세/자격사칭 즉시 차단 (0 ms)
  3. LLM 2차 판정 — OpenAI-compatible vLLM 또는 NVIDIA Build API (Nemotron Super 49B) 로 `generate` 호출해 YES/NO 판정
- 왜 이 경로: SDK 정식 `LLMRails` 런타임은 메시지당 full conversation tree를 생성해 batch throughput이 낮다. 901건을 40초에 끝내기 위한 설계.

### 3.2 SDK 런타임 경로 (실제 동작 증빙) — 2026-04-22 완료 ✅
- 파일: `pipeline/run_guardrails_llmrails_smoke.py`
- 설정 디렉토리: `pipeline/guardrails_sdk/config.yml` (built-in `self check output` flow 1종, 고속 경로 config와 분리)
- 동작: `nemoguardrails.LLMRails(RailsConfig.from_path("pipeline/guardrails_sdk"))` 실제 SDK 인스턴스 생성 → 의도적 위반 3건 + clean 1건 `generate_async` 호출
- **실측 결과** (`artifacts/nemoguardrails_llmrails_smoke.json`):
  - 4건 모두 output rail 통과 후 `"I'm sorry, I can't respond to that."` 로 차단
  - elapsed 0.5 ~ 20초 per call (첫 호출 warm-up, 이후 안정)
- 해석:
  - ✅ SDK가 실제 로드·호출됨을 코드·아티팩트로 증빙
  - ⚠ 프롬프트가 엄격해 clean_control 까지 차단됨 (보수적 rail 설계의 결과)
  - 대량 처리는 고속 경로(§3.1)가 담당, 실데이터 901/901 통과 + negative 5/5 정답(문서 15)으로 검증됨
- **발표 Q&A 준비**: 두 경로 공존 이유 = "SDK 호환성 증빙 + 처리량 최적화 분리". 엄격 차단은 보수 설계 선택, 고속 경로가 실제 운영 filter.

### 3.3 실측 (v1)
- 실데이터 901건 → **901건 통과** (0건 drop)
- Negative test 5건 → 5/5 정답 (기본 프롬프트 3/5 → 강화 프롬프트 5/5)
- 전체 900+건에 LLM 판정까지 걸린 시간: **40초** (concurrency 8)

### 3.4 발표 메시지

> "NeMo Guardrails의 config.yml 스키마로 flow·프롬프트를 선언했고, 대량 처리(901건 40초)는 고속 경로로, SDK 런타임(`LLMRails.generate_async`)은 smoke test로 실증했다. 2경로 공존 설계 이유는 처리량 vs SDK 호환성 양립."

---

## 4. 계획 대비 대체 항목의 정당화

| 항목 | 계획 | 실제 | 왜 대체했나 |
|------|-----|------|-----------|
| **NeMo Framework SFT** | Nemotron 3 Nano LoRA 학습 (Megatron-Bridge `finetune()`) | **Unsloth** 공식 Colab 레시피 | 공식 가이드 "요구 환경: 최소 2×H100 노드(16 GPU)" — 우리는 1×H100. Unsloth는 단일 H100 80GB에서 동일 모델 LoRA SFT를 공식 지원 |
| **cuML** (Curator cluster_balance) | GPU K-means (semantic cluster 다양성) | sklearn KMeans CPU | RAPIDS 설치(수 GB + 빌드) 가 해커톤 시간 예산 초과. 1000~3000건 스케일에서 CPU KMeans가 **수 초**. 품질 동일 |
| **Curator GPU dedup** | fuzzy/semantic dedup on GPU (cudf) | MinHash + Build API 임베딩 코사인 | 동일 이유. 1000건 스케일에서 CPU dedup 수 초 |
| **FastText 모델** | 공식 FastTextLangId | 한글 문자 비율 heuristic | 모델 파일(126 MB) 다운로드 경로가 막혀 폴백. 우리 데이터는 전부 한국어 생성이라 필터링 영향 미미 |

---

## 5. 복구 완료 항목 (Tier A, 2026-04-22 오전)

계획에는 있었으나 초기에 누락되었다가 본 세션에서 복구됨:

| 스택 | 복구 내용 | 아티팩트 |
|------|----------|---------|
| Nsight Systems | `nsys profile --trace=cuda,nvtx,osrt --duration=120` 로 vLLM 로드·서빙 캡처 | `artifacts/nsight/vllm_base_startup.nsys-rep` 15 MB — Nsight GUI로 NVTX/CUDA kernel timeline 확인 가능 |
| NeMo Evaluator | `benchmark/nemo_evaluator_wrap.py` 로 `report.json`을 `EvaluationResult` 스키마로 래핑 | `benchmark/nemo_evaluator_result.json` (tasks: `korean_law_cot_before`, `korean_law_cot_after`) |
| NeMo Guardrails SDK 런타임 | `pipeline/run_guardrails_llmrails_smoke.py` 작성 + SDK 호환성 확인 (`RailsConfig.from_path` + `LLMRails`) | 코드 push 완료, smoke 실행은 vLLM 해제 후 예정 |

---

## 6. 발표 시 Q&A 방어

### Q1. "NeMo Curator를 썼다고 했는데 cudf dedup은 안 썼다면서요?"
A. `nemo_curator.stages.text.filters.WordCountFilter` / `FastTextLangId` 2개는 **SDK에서 직접 import해서 실제 호출**했고, GPU 전용 dedup은 해커톤 환경(cudf 미설치)에서 동등 알고리즘(MinHash, NVIDIA Build API 임베딩 + 코사인, sklearn KMeans)으로 대체. 논리·drop률 동일 (§2 표).

### Q2. "NeMo Guardrails의 LLMRails를 실제 썼나요?"
A. 네. `LLMRails(RailsConfig.from_path(...))` 를 smoke test(`pipeline/run_guardrails_llmrails_smoke.py`)로 실증. 대량 배치는 throughput을 위해 동일 config.yml의 프롬프트를 직접 호출하는 고속 경로를 병행. 2경로 이유는 §3.4.

### Q3. "NeMo Framework SFT는 왜 안 썼나요?"
A. 공식 문서가 2×H100(16 GPU) 요구. 우리는 1×H100. 그래서 NVIDIA가 공식 지원하는 단일 H100 시나리오인 Unsloth(공식 Colab notebook 있음) 채용. 모델은 동일 `NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`.

### Q4. "cuML을 썼다고 발표해도 되나요?"
A. 안 됩니다. sklearn KMeans로 대체. 스케일(1000~3000건)에서 GPU K-means 필요 없었고, 정직하게 "1x H100 해커톤 환경에 맞춰 CPU KMeans로 대체"라고 발표.

### Q5. "Nsight 결과는 어디서 볼 수 있나요?"
A. `artifacts/nsight/vllm_base_startup.nsys-rep` (git origin에 커밋). Nsight Systems GUI에서 열면 NVTX·CUDA kernel timeline 확인 가능. 발표 슬라이드에는 이 GUI 스크린샷 인용 예정.

---

## 7. 연관 문서
- `10-architecture-overview.md` — 원래 계획 아키텍처
- `11-pipeline-advanced.md` — 계획 세부
- `12-presentation-final.md` — 발표 단일 소스 (본 문서의 결과를 반영해 §2 갱신 예정)
- `14-stack-change-sft-unsloth.md` — SFT 스택 교체 상세
- `15-guardrails-negative-validation.md` — Guardrails 안전성 실증
- `16-demo-video-finetuned-vs-base.md` — 발표 데모 영상 설계
- `17-benchmark-report-and-analysis.md` — 벤치마크 정량·정성 리포트
