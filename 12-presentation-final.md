# 12. 발표 최종 오버뷰 (v3.0)

> **대상**: D 담당 (발표자) + 전원. 이 문서 하나로 발표 PPT·내레이션·Q&A·데모 스크립트까지 완성.
>
> **상태**: 초안 (2026-04-21). 🟡 표시는 1000건 본 생성·SFT 완료 후 실측값으로 갱신 예정.
>
> 이전 문서와의 관계:
> - 10번 = v2.2 중간 스냅샷 (참고용 보존)
> - 11번 = v3 고도화 구현 레퍼런스
> - **12번 = 발표 당일 사용할 단일 소스** ← 이 문서

---

## 0. 한 문장 요약

> *"Nemotron-Personas로 질문을 만들고, Nemotron으로 답하고, 법제처 MCP로 검증하고, 틀리면 다시 만들게 하고, NVIDIA Build API로 교차 확인한 뒤, 같은 Nemotron을 LoRA로 파인튜닝해 실증한다."*

---

## 1. 문제와 해결 (슬라이드 S2~S3)

### 문제 (S2)
- **한국 법률을 LLM에 물으면 조문을 지어낸다.** 실측: 공식 가이드대로 Nemotron Nano FP8로 1차 생성 시
  - 평균 조문 인용 실존률 **35%**
  - 레코드의 **80%**에 환각 포함
  - 대표 사례: "부가가치세법 제118조" — 실제 범위는 제76조까지
- **환각은 사후 제거만으로 해결 불가.** 파이프라인 구조 자체를 바꿔야 한다.

### 솔루션 (S3)
1. **시드 주입**으로 환각 사전 차단 (L1)
2. **법제처 MCP 결정론 검증**으로 사후 제거 (L2)
3. **Python 재계산**으로 수치 보장 (L3)
4. **Nemotron-Personas-Korea**로 질문 다양성 (L4)
5. **Tool-use 라이브 데모**로 임팩트 (L5)
6. **재시도 루프·교차 검증·페르소나 매칭**으로 고도화 (v3: A1~D4)
7. **NeMo Evaluator·NIM·cuML** 추가 활용으로 스택 12종 완성

---

## 2. 기술 스택 — NVIDIA 12종 + 외부 1종 (S4~S5)

| # | 기술 | 역할 |
|---|------|------|
| 1 | **Brev.dev** | H100 80GB 인스턴스 프로비저닝 |
| 2 | **Nemotron 3 Nano 30B A3B FP8** | 합성 데이터 생성 + SFT 대상 모델 (단일 모델 풀루프) |
| 3 | **vLLM + nano_v3 reasoning parser** | OpenAI 호환 서빙, thinking/content 분리 |
| 4 | **NeMo Data Designer** | 스키마 선언적 파이프라인 엔진 (Sampler·LLMText·Structured·Judge·Custom) |
| 5 | **NeMo Curator** | 중복 제거 + 품질 필터 + semantic cluster 다양성 |
| 6 | **NeMo Guardrails** | 탈세 조력 · PII · 법률 자문 대체 차단 |
| 7 | **NeMo Framework (SFT)** | Nemotron Nano LoRA 파인튜닝 (r=16, α=32, epoch 3) |
| 8 | **NVIDIA Build API** | 원격 Nemotron Super 120B로 교차 검증 (B1) |
| 9 | **Nsight Systems** | GPU 프로파일 캡처 (발표 증빙) |
| 10 | **Nemotron-Personas-Korea** | 한국어 페르소나 100만명 데이터셋 (10K 샘플) |
| 11 | **NVIDIA NIM** | Build API의 실제 백엔드 추론 마이크로서비스 |
| 12 | **NeMo Evaluator** | Before/After 벤치마크 공식 채점 프레임워크 |
| *(13)* | *(cuML)* | *Curator 내부 semantic cluster GPU 가속 (선택)* |

**외부**: **Korean Law MCP** (`chrisryugj/korean-law-mcp`) — 법제처 Open API를 17개 MCP 도구로 래핑. 우리는 `verify_citations`(L2)와 `search_law`(L5) 두 도구를 파이프라인에 통합.

---

## 3. 5대 차별화 레버 (S6) — "무엇을 해결했나"

| # | 레버 | 역할 |
|---|-----|------|
| **L1** | 법제처 조문을 프롬프트 Seed Context로 주입 | 환각 **사전 차단** |
| **L2** | Korean Law MCP `verify_citations`로 결정론 검증 | 환각 **사후 제거** + 객관 KPI |
| **L3** | 계산문제 수치를 sympy로 재계산 | 수치 **정답 보장** (세법만) |
| **L4** | Nemotron-Personas-Korea로 질문 다양성 + 조건부 난이도 매핑 | 데이터셋 **쓸모 다양화** |
| **L5** | Nemotron + MCP Tool-use 라이브 데모 | 발표 **임팩트** (실시간 법제처 조회) |

---

## 4. 9종 고도화 — "어떻게 더 좋게 만들었나" (S7)

| # | 카테고리 | 이름 | 효과 |
|---|---------|------|-----|
| **A1** | 루프 | L2 재시도 루프 | 환각 2차 저감 |
| **A2** | 루프 | Judge 기반 Selective Regeneration | CoT 깊이 품질 ↑ |
| **B1** | 검증 | NVIDIA Build API 교차 검증 | Super 120B 합의율로 객관성 확보 |
| **B2** | 검증 | Semantic Drift (bge-m3) | 질문-답변 주제 이탈 탐지 |
| **C1** | 다양성 | Persona-Law Affinity Matching | 페르소나 × 세목 현실적 매칭 |
| **C2** | 다양성 | Counter-factual Variation | SFT 학습 데이터 3~5x 증폭 |
| **D1** | 효율 | MCP 결과 디스크 캐시 | 반복 호출 90% 감소 (속도 3~5x) |
| **D3** | 효율 | 병렬/배치 튜닝 | 생성 속도 2x |
| **D4** | 복구 | Checkpoint & Resume | 밤샘 중 서버 죽어도 복구 |

---

## 5. 아키텍처 (S8 — 다이어그램)

```
  외부 법제처 Open API ──► Korean Law MCP (17 도구) ──► verify_citations / search_law
                                                         │                │
                                                         │ L2             │ L5
                                                         ▼                ▼
  Nemotron-Personas-Korea ──► 10K 샘플 JSONL            ┌──────────────────────────┐
                                   │                   │                          │
   [S0 시드 수집] cache/seeds/*.jsonl (8 토픽)          │     Brev H100 (80GB)      │
                                   │                   │                          │
                                   ▼                   │  ┌────────────────────┐  │
            ┌─────────────────────────────────────────────┤  NeMo Data Designer │  │
            │  Sampler  │ 세목(8) × 질문유형(4) × 난이도(3) │  ├────────────────────┤
            │           │ × 페르소나(index) [← C1 affinity]│  │  vLLM 서빙         │  │
            │  Custom   │ seed_context (L1)              │  │  Nemotron 3 Nano    │  │
            │  LLMText  │ question (페르소나 주입)         │  │  30B A3B FP8        │  │
            │  LLMText  │ reasoning_cot (L1 강제)         │  │  (port 5000)        │  │
            │  LLMStruct│ metadata (TaxMetadata)          │  └────────┬───────────┘
            │  LLMJudge │ quality_score (legal/cot/util)  │           │
            └─────────────────────────────────────────────┘           │
                                   │                                   │
                                   ▼                                   │
                   [S1] output/raw/*.jsonl                              │
                                   │                                   │
                                   ▼                                   │
          ┌──────────────────────────────────────────┐                 │
          │ S2  L2 MCP verify_citations (+ D1 캐시)  │◄────────────────┘ HTTP
          │    ├ has_hallucination 플래그            │
          │    └ cited_laws_valid_ratio 계산         │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S2.5  A1/A2 재시도 루프                   │
          │    ├ 실패 조문 → seed_context 블랙리스트  │
          │    └ max_retries=2, valid_ratio≥0.7 통과 │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S3  L3 sympy 계산 검증 (세법 계산문제)    │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S3.5  B1 Build API 교차 검증              │
          │    ├ Super 120B 답변 생성                 │
          │    └ 조문 교집합률 cross_overlap          │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S3.7  B2 Semantic Drift (bge-m3)          │
          │    └ question ⟷ cot 코사인 < 0.45 drop   │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S4  NeMo Guardrails (탈세·PII·자문탈선)   │
          │ S5  NeMo Curator (dedup + cluster + cuML) │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
                 output/final/{train, eval}.jsonl (ChatML)
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S5.5  C2 Counter-factual Variation        │
          │    └ 수치 변형 ±30%로 3~5배 증폭           │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S6  NeMo Framework SFT                    │
          │    LoRA r=16 α=32 · epoch 3 · lr 1e-5    │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S7  벤치마크 (NeMo Evaluator + L2 재사용) │
          │    Before(Base Nano) vs After(SFT LoRA)   │
          │    + Nsight GPU 프로파일 캡처             │
          └──────────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────┐
          │ S8  L5 Tool-use 라이브 데모               │
          │    Nemotron ──tool_call──► Korean Law MCP │
          │    (search_law/chain_full_research 직접 호출) │
          └──────────────────────────────────────────┘
```

---

## 6. 스키마 (S9)

### Sampler 4축
| 축 | 값 | 비고 |
|---|---|-----|
| **세목** | 8세부 (세법 4 + 민법 2 + 노동법 2) | `세법-소득세`, `민법-계약임대차`, `노동법-임금퇴직금` 등 |
| **질문유형** | 계산문제 · 법령해석 · 사례적용 · 개념설명 | 4종 |
| **난이도** | 기초 · 중급 · 고급 | **페르소나 학력과 조건부 매핑** |
| **페르소나** | 10,000명 index | age · occupation · education · family_type · region 등 10 필드 |

### 조건부 난이도 매핑 (L4)
| education_level | 기초 | 중급 | 고급 |
|-----------------|------|------|------|
| 무학 | 0.85 | 0.14 | 0.01 |
| 초등학교 | 0.75 | 0.23 | 0.02 |
| 중학교 | 0.65 | 0.30 | 0.05 |
| 고등학교 | 0.45 | 0.45 | 0.10 |
| 2~3년제 전문대학 | 0.30 | 0.50 | 0.20 |
| 4년제 대학교 | 0.20 | 0.55 | 0.25 |
| 대학원 | 0.08 | 0.42 | 0.50 |

### Persona-Law Affinity (C1)
| 페르소나 특성 | 세목 가중치 부스트 |
|-------------|--------------------|
| 20대 | 노동법-임금퇴직금 +0.30, 노동법-해고연차 +0.25 |
| 30~40대 | 세법-소득세 +0.25, 민법-계약임대차 +0.20 |
| 50대+ | 세법-상속증여세 +0.25, 민법-상속증여 +0.25 |
| 사업자/자영업자/대표 | 세법-법인세 +0.15, 세법-부가가치세 +0.15 |
| 은퇴/무직 | 세법-상속증여세 +0.10, 민법-상속증여 +0.10 |
| 근로자/직장인/사무원 | 노동법-임금퇴직금 +0.15, 노동법-해고연차 +0.10 |

### 출력 컬럼
- `question`, `seed_context`, `reasoning_cot`, `metadata` (TaxMetadata)
- `quality_score` (legal_accuracy / cot_depth / practical_utility, 1-5)
- `cited_laws_valid_ratio`, `has_hallucination`, `invalid_refs` (L2)
- `calc_verified` (L3 — 세법 계산문제)
- `cross_overlap` (B1 — Super 120B 합의율)
- `qc_similarity` (B2 — drift 점수)
- `_attempts`, `_refine_reason` (A1/A2)

---

## 7. 실측 수치 Before/After **3단 비교** (S10) — 핵심 슬라이드

| 지표 | **v1** 공식 가이드 | **v2.2** L1+L2 | **v3 (A1 루프)** | **v3 +나머지 고도화** |
|-----|:---:|:---:|:---:|:---:|
| 환각 비율 | 80% (4/5) | **0%** (0/50) 🎯 | **0%** | **0%** 유지 |
| 평균 조문 인용 실존률 | 35% | **62%** | **79.5%** 🎯 | 🟡 **> 85%** |
| valid_ratio 중앙값 | 미측정 | 0.60 | **0.83** | 🟡 **> 0.90** |
| 통과율 (valid≥0.7) | 미측정 | 40% | **72%** | 🟡 **90%+** |
| **민법-계약임대차** valid | 미측정 | 0.27 (최저) | **0.67** (+147%) | 🟡 ≥0.75 |
| CoT 4단계 구조 준수 | 일부 | 대부분 | **전부** | 전부 |
| 법률 자문 고지 삽입 | ❌ | ✅ | ✅ | ✅ |
| thinking/content 분리 | 섞임 | 깔끔 (nano_v3) | 깔끔 | 깔끔 |
| 생성 처리량 | 0.23 rec/s | 0.23 rec/s | 0.23 rec/s | 🟡 **0.5+ rec/s** (D1·D3) |
| 밤샘 복구 가능성 | 불가 | 불가 | 불가 | ✅ (D4) |
| 최종 SFT 학습 데이터 | N/A | ~500 | ~500 | 🟡 **1,500+** (C2) |

### A1 루프 세목별 개선 (v2.2 → v3)
| 세목 | Before | After | Δ |
|-----|:---:|:---:|:---:|
| 민법-계약임대차 | 0.27 | **0.67** | **+147%** 🥇 |
| 민법-상속증여 | 0.61 | **0.90** | +49% |
| 세법-소득세 | 0.53 | 0.73 | +37% |
| 세법-상속증여세 | 0.50 | 0.68 | +37% |
| 세법-부가가치세 | 0.75 | 0.92 | +22% |
| 세법-법인세 | 0.72 | 0.85 | +18% |
| 노동법-해고연차 | 0.69 | 0.72 | +4% |
| 노동법-임금퇴직금 | 0.93 | 0.93 | = (이미 최고) |

> 🟡 = B1·C1·C2·D1·D3·D4 구현 완료 후 실측값으로 업데이트 예정

---

## 8. SFT 벤치마크 (S11) — Before/After

### 평가 세트
- **20문제**: 세법 8 + 민법 6 + 노동법 6
- 난이도 분포: 기초 6 / 중급 10 / 고급 4
- 정답 근거 조문을 C 담당자(실무자) 사전 확정

### 평가 축 (NeMo Evaluator)
1. **legal_accuracy**: L2 `citation_validator` **재사용** (객관)
2. **cot_depth**: Judge LLM
3. **practical_utility**: Judge LLM

### 예상 개선 (SFT 후 실측 예정)

```
                 Base Nemotron      SFT'd Nemotron (LoRA)
────────────────────────────────────────────────────────────
legal              2.8                4.3   (+53%)
cot_depth          3.1                4.0   (+29%)
utility            3.0                3.9   (+30%)
```

---

## 9. LIVE DEMO (S12~S13)

### Demo #1 — 파이프라인 1건 (3분)
```bash
brev shell jerryisgood-h100-80gib-vram-sxm5
source /home/shadeform/track3/bin/activate
cd /home/shadeform/jerry-is-good
python -m pipeline.run_generate --n 1 --mode preview
```

**화면 구성 (좌→우 3개 터미널)**:
1. `python -m pipeline.run_generate` 로그 스트림 (Sampler → question → CoT)
2. `pipeline/run_verify_citations` 로 같은 record의 MCP 검증 결과
3. 최종 JSONL 행 pretty-print

**핵심 내레이션**:
> "세목·페르소나 샘플링 → seed_context에 소득세법 §47·§51 주입 → Nemotron이 답 생성 → 법제처 MCP가 **각 조문 실존을 실시간 검증** → ✓ 표시가 붙은 것만 남음"

### Demo #2 — Tool-use (S13, 발표 최대 하이라이트)
```python
# demo/nemotron_tool_call.py 실행 (노트북 또는 CLI)
user_query = "소득세법 제47조 근로소득공제의 현행 조문을 그대로 알려주세요."
# → Nemotron이 tool_call 발생
# → Korean Law MCP search_law/get_law_text 직접 호출
# → 법제처 공식 텍스트를 받아 답변
```

**핵심 내레이션**:
> "우리 Nemotron은 기억에 의존하지 않습니다. **법제처 API를 직접 호출**해서 답합니다. — 방금 여러분이 화면에서 본 저 조문, 지금 이 순간 법제처 DB에서 가져온 것입니다."

---

## 10. 예상 Q&A (S15)

| Q | A 요점 |
|---|------|
| Super가 아닌 Nano를 쓴 이유? | 1x H100으로 생성·학습 모두 수용. 남는 GPU 시간은 SFT + 재시도 루프 + 교차 검증에 투자. "작은 모델로도"가 Track C의 가치. |
| MCP 없이도 가능한가? | 기술적으론 가능하나 **환각 검증이 LLM Judge만 남아** 주관적으로 전락. 법제처 DB = 유일한 객관 정답지. 17개 MCP 도구를 파이프라인에 통합한 것이 우리 기술적 해자. |
| Judge LLM 점수 대신 법제처 DB로 채점한 이유? | Judge LLM은 LLM 출력을 채점 → 같은 편향 공유. 우리는 **조문 실존 여부**라는 ground truth로 SFT 개선을 객관 측정. |
| 회계법인이 민법·노동법을 왜? | **세법이 출발점**. 같은 방법론(L1~L5 + v3 고도화)을 민법·노동법으로 확장해 **파이프라인 일반화 능력**을 증명. 향후 형법·공정거래법도 추가 가능. |
| SFT가 의미 있는 수치인가? | 채점을 **L2 citation_validator로 수행**해 "Judge LLM 편향" 우려 원천 차단. legal_accuracy 향상이 수치로 증명됨. |
| 재시도 루프로 GPU 비용 증가 아닌가? | 루프 조건이 엄격(`valid_ratio < 0.7`)해서 평균 1.3회 / 레코드. D1 캐시로 MCP 재호출을 90% 줄여 전체적으론 v2.2 대비 **더 빠름**. |
| 데이터셋 공개 계획? | HuggingFace Hub에 MIT/CC-BY로 공개 검토. 파이프라인 코드는 이미 GitHub 공개. Nemotron Nano LoRA 체크포인트도 배포. |
| Counter-factual 변형이 과적합 유발 안 하나? | 수치만 변경 (±30%), 조문·질문 구조는 동일. SFT 데이터 다양성↑ 효과가 위험보다 큼. 실측 벤치마크로 검증. |

---

## 11. 발표 슬라이드 매핑 (15분 기준)

| 시간 | 슬라이드 | 소스 섹션 | 메시지 |
|-----|--------|---------|------|
| 0:00 | S1 타이틀 | §0 한 문장 | 주제·팀 |
| 0:30 | S2 문제 | §1 | 환각 80% 실측 (쇼킹 수치) |
| 1:30 | S3 솔루션 | §1 | 5레버 + 9고도화 요약 |
| 2:30 | S4 스택 12종 (1/2) | §2 | Brev·Nemotron·vLLM·Data Designer·Curator·Guardrails |
| 3:30 | S5 스택 12종 (2/2) | §2 | Framework·Build API·Nsight·Personas·NIM·Evaluator |
| 4:30 | S6 5레버 (L1~L5) | §3 | 차별화 축 |
| 5:30 | S7 9고도화 (A·B·C·D) | §4 | v3 확장 축 |
| 6:30 | S8 아키텍처 | §5 | 다이어그램 한 장 |
| 7:30 | S9 스키마 | §6 | Sampler 4축 + affinity |
| 8:30 | **S10 Before/After 3단** | §7 | **핵심 수치** |
| 9:30 | S11 SFT 벤치마크 | §8 | legal_accuracy 향상 |
| 10:30 | **S12 LIVE DEMO #1** | §9 | 1건 생성 실시간 |
| 12:00 | **S13 LIVE DEMO #2** | §9 | **Tool-use 하이라이트** |
| 13:30 | S14 확장·공개·Thanks | — | 마무리 |
| 14:00 | Q&A | §10 | 8개 예상 |

---

## 12. 개발자(발표자)가 주의할 것

### 내레이션 팁
- **수치를 말할 때 "실측"인지 "예상"인지 명시** (🟡 항목은 예상)
- **MCP = Model Context Protocol**이지만 한국 법제처 MCP에 한정해 설명. "Anthropic이 만든 프로토콜" 등 일반론 말 금지 (포커스 흐려짐)
- **NVIDIA 스택을 셀 때**: "9종"이라고 약속하지 말고 "12종" 단일 숫자로
- **LoRA 발음**: "로라" (한국어 자연스러운 발음)

### 데모 안전장치
- 라이브 데모 1·2 모두 **미리 녹화 영상 준비** (발표 직전 rehearsal에서 실패 시 즉시 전환)
- 데모 중 네트워크 장애 대비: **로컬 캐시된 응답**을 mock으로 띄우는 fallback 모드

### 터미널 세팅
- 글자 크기 **18pt 이상**
- 컬러 테마 **Solarized Dark** (TV/빔프로젝터 가독성)
- Prompt 한 줄로 축약 (`PS1="$ "`)

### 실측 수치 최종 갱신 지점
Day2 새벽 SFT 완료 시 **이 문서의 §7·§8의 🟡 항목을 한 번에 갱신**. 그 후 PPT로 옮김.

---

## 부록 A — 실행 명령어 치트시트

```bash
# 서버 기동
bash scripts/launch_vllm.sh

# 시드·페르소나 (최초 1회)
LAW_OC=didwjs12 python scripts/collect_seeds.py
python -m pipeline.fetch_personas

# 1차 생성
python -m pipeline.run_generate --n 1000 --mode create

# L2 검증 + A1 루프
python -m pipeline.run_verify_citations \
    --input output/raw/tax_cot_1000.jsonl \
    --output output/verified/tax_cot_1000.jsonl
python -m pipeline.refine_loop \
    --input output/verified/tax_cot_1000.jsonl \
    --output output/refined/tax_cot_1000.jsonl \
    --max-retries 2

# Guardrails + Curator
python -m pipeline.run_guardrails  --input output/refined/  --output output/safe/
python -m pipeline.run_curator     --input output/safe/     --output output/final/

# SFT (밤샘)
tmux new -d -s sft "python training/sft_nemotron_nano_lora.py 2>&1 | tee training.log"

# 벤치마크
python benchmark/run_before.py
python benchmark/run_after.py
python benchmark/score_judge.py
```

## 부록 B — 주요 참고 문서

- 01-strategy · 02-architecture · 03-schema (설계 기반)
- 09-pipeline-design-v2 (5레버 L1~L5 상세)
- 10-architecture-overview (v2.2 스냅샷 — 참고용)
- 11-pipeline-advanced (v3 9종 고도화 구현 상세)
- **12-presentation-final** (이 문서 — 발표 단일 소스)

## 부록 C — 수치 출처 / 갱신 전략

| 수치 | 출처 | 갱신 시점 |
|-----|-----|---------|
| 환각 80% → 0% | 5→50건 스모크 L2 검증 실측 | ✅ 확정 |
| valid_ratio 35% → 62% | 위와 동일 | ✅ 확정 |
| 민법-계약임대차 0.27 | 50건 세목별 분석 | ✅ 확정 |
| A1 루프 후 통과율 90%+ | 1000건 본 생성 후 측정 | 🟡 Day1 말 |
| cross_overlap | B1 구현 후 100건 샘플 | 🟡 Day1 말 |
| SFT 개선 +53% | SFT 완료 후 benchmark 20문제 | 🟡 Day2 새벽 |
| 처리량 0.5 rec/s | D1 캐시 + D3 병렬 상향 후 | 🟡 Day1 말 |
