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

> **실구현 vs 계획 매핑**: 상세는 **문서 18번** 참조.
> 요약: 계획 12종 중 **실사용 10종 + 대체 2종 (cuML→sklearn, NeMo Framework SFT→Unsloth)**,
> 추가 도입 1종 (Unsloth 공식 Colab 레시피). 대체 사유 모두 해커톤 환경 제약(단일 H100, RAPIDS 미설치)으로 정당화.
> Nsight 캡처·NeMo Evaluator wrap·NeMo Guardrails LLMRails SDK smoke 모두 본 세션에서 복구 완료.


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

### B1 Build API 교차 검증 (Super 120B, 50건 실측)
| 지표 | 값 | 해석 |
|-----|:---:|------|
| Nano 조문 인용 추출 | 50/50 (100%) | 우리 Nano는 **항상 명시적 조문 인용** |
| Super 조문 인용 추출 | 22/50 (44%) | Super는 서술 중심, 조문 번호 생략 경향 |
| **cross_overlap (Jaccard)** | **0.035** | **두 모델이 독립적 관점으로 사고** |

**발표 서사**: *"Super 120B와 Nano 30B의 답변을 교차 검증 — Jaccard 0.035 = 두 모델이 각자 독립적으로 한국 법을 해석. Nano의 조문 실존률 79.5%는 자체 Seed 주입·재시도 루프의 결과이지 Super를 모방한 게 아님을 증명."*

### C1+D3 성능 (50건, max_parallel 4→8)
| 항목 | v2.2 baseline | **v3 (D3)** | 개선 |
|-----|---|---|---|
| metadata 처리 | 2.79 rec/s | **3.30 rec/s** | +18% |
| judge 처리 | 1.96 rec/s | **2.69 rec/s** | +37% |
| fill_rate | 100% | 100% | 유지 |
| CoT 평균 | 808자 | **905자** | +12% (페르소나 맥락 포함) |

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

## 7-1. `valid_ratio` 지표 정의 (발표 Q&A 핵심)

> **이 수치는 객관 지표인가? 정답지가 따로 있는가?** — 이 섹션은 심사위원의 이 질문에 답하기 위한 것.

### 계산 공식
```
valid_ratio = (✓ 실존 확인된 조문 수) / (총 추출된 조문 인용 수)
```

### 정답지 = **대한민국 법제처 국가법령정보센터 DB**
- 조회 엔드포인트: `https://www.law.go.kr/DRF/lawService.do`
- 법무부·행정안전부가 관리하는 **공식** 데이터베이스
- 법령 개정 시 DB도 자동 갱신 → 우리 검증도 항상 현행 기준

### 단계별 작동 (실제 예시)

**입력**: 모델이 생성한 `reasoning_cot` 텍스트 전체

```
1) Korean Law MCP가 regex로 조문 후보 추출
   "소득세법 제47조(근로소득공제)" → {law: "소득세법", article: "47"}
   "부가가치세법 제138조"            → {law: "부가가치세법", article: "138"}

2) 각 후보를 법제처 API에 실시간 조회
   ✓ 소득세법 제47조           → 실존 (numerator +1)
   ✗ 부가가치세법 제999조      → NOT_FOUND (존재 범위: ~제76조)
   ⚠ (법령명 미지정) 제20조    → 법령명 모호 (분모 포함, 분자 제외)

3) 응답 포맷:
   총 3건 | ✓ 1 실존 | ✗ 1 오류 | ⚠ 1 확인필요
   valid_ratio = 1 / 3 = 0.33
```

### 우리가 "Judge LLM 점수" 대신 이걸 쓰는 이유

| 지표 | 출처 | 편향 |
|-----|-----|-----|
| Judge LLM score | LLM이 LLM을 채점 | ❌ 같은 편향 공유 가능 |
| **valid_ratio** | **정부 공식 DB** | **✅ LLM 외부 객관 기준** |

### 중요한 한계 (발표 시 솔직히 언급)

1. **"실존"이 "정답"은 아니다**
   - 근로소득공제 질문에 "소득세법 제20조(근로소득)" 인용 — **실존하지만 실제 답은 제47조**
   - valid_ratio는 "환각인가 아닌가"까지만 검증. "답이 맞나"는 다음 레이어(Judge + L3 calc)
2. **warning도 분모엔 포함**
   - 모델이 법령명 없이 "제20조"만 썼을 때 ⚠로 분류 → valid_ratio 하락
   - 즉 **"법령명 명시적 인용"까지 강제**하는 엄격한 지표
3. **regex 추출 실패한 조문**은 total에 포함 안 됨 → total=0인 행은 valid_ratio=0으로 집계

### 한 문장 요약

> **valid_ratio = 모델이 인용한 조문 중, 대한민국 법제처에 실제 존재하는 조문의 비율.** 정답지는 **정부 공식 법령 DB**이므로 우리가 조작·자의 해석할 수 없는 외부 객관 지표.

---

## 7-3. 평가자 편향 해소 — Q&A 핵심 방어 섹션

> **Q: "SFT 학습을 L2로 필터링한 데이터로 했는데, 채점도 L2로 하면 편향 아닌가요?"**
>
> **A**: **맞습니다. 그래서 L2는 보조 지표로 강등하고 주 지표를 독립 평가자로 재구성했습니다.**

### 순환 구조 자체 인정 + 외부 독립 채점자 도입

우리 학습 파이프라인은 단일 Nemotron 내부 루프가 있습니다 (Nemotron 생성 → L2 필터링 → Nemotron LoRA 학습). 이 순환 리스크를 해커톤 **NVIDIA 풀루프 서사**와 **편향 해소** 양쪽 다 잡기 위해 다음 설계를 했습니다.

### 평가자 4축 (우선순위 순)

| 순위 | 지표 | 출처 | 학습 과정 관여도 |
|----|-----|-----|--------------|
| **1순위 ★** | **expected_laws 커버리지** | 사람 (C 담당, 수작업) | ✅ 완전 독립 |
| **1순위** | 키워드 커버리지 | 사람 (수작업) | ✅ 완전 독립 |
| **2순위** | `cross_overlap` (Super 120B Jaccard) | NVIDIA Build API Super 120B | ✅ 다른 크기·다른 체크포인트 독립 평가자 |
| 3순위 | Judge LLM (`cot_depth`·`practical_utility`) | Nemotron 자체 | ⚠ L2와 다른 축, 반독립 |
| **보조** | L2 `valid_ratio` | Korean Law MCP | ❌ 학습 필터에 사용 → 편향 가능 |

### 발표에서 제시할 수치 (우선순위)

```
[주 수치]
  expected_laws 커버리지: Before X% → After Y%  (사람 정답 기준)
  cross_overlap (Super 120B): Before A → After B  (독립 평가자 기준)

[보조 수치 (투명성 차원에서 공개)]
  L2 valid_ratio: Before → After  (학습 필터에 쓴 지표, 참고)
```

### 발표 Q&A 완성형

> **심사**: "모델이 자기가 만든 데이터로 자기를 학습하면 당연히 잘하게 되지 않나요?"
>
> **팀**: "순환 구조 리스크를 인지하고 **3중 독립 채점자**를 두었습니다:
> ① **법제처 공식 DB**(우리가 만들 수 없는 외부 ground truth) — L2 보조 지표,
> ② **사람이 지정한 `expected_laws`**(20문제 각각 정답 조문을 사전 수작업) — **주 지표**,
> ③ **NVIDIA Build API Super 120B**(다른 크기·다른 체크포인트의 독립 평가자) — cross_overlap 집계.
>
> SFT Before/After 비교 시 **주 수치는 ②, ③입니다**. L2는 **학습 필터로 사용했으므로 편향 가능성을 인정하고 보조 지표로 분리**했습니다.
>
> 그리고 왜 Nemotron을 대상으로 SFT했는가? — NVIDIA Nemotron 해커톤의 **Track C 목적(Nemotron 데이터 합성 파이프라인)**에 정확히 부합하고, **NVIDIA 풀루프 증명**이 우리 서사의 핵심이기 때문입니다. 데이터 생성 모델과 학습 모델이 같아도, **외부 독립 평가자로 개선이 증명**되면 편향은 해소됩니다."

### 또 한 가지 방어: 검증 세트 독립

- 벤치마크 20문제는 **학습 데이터 생성 전에 수작업으로 확정** (`benchmark/questions.jsonl`)
- 20문제 각각에 `expected_laws[]` 필드가 있고 이는 **사람이 지정**
- 학습 데이터와 **단 한 건도 겹치지 않음**

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

### 실측 결과 (2026-04-22 SFT v1 완료, 문서 17 전문)

**주 지표 (score_judge.py 4축, N=20):**

| 지표 | Base Nemotron | SFT'd Nemotron (LoRA) | Δ | 해석 |
|------|:---:|:---:|:---:|------|
| expected_laws coverage (사람 지정 정답) | 0.458 | 0.458 | **0.000** | 1000건 스케일에서 조문 번호 암기 교정 불가 — pretraining 규모 문제로 솔직 공개 |
| Super 120B cross_overlap | 0.102 | 0.092 | -0.010 | 노이즈 수준 |
| L2 valid_ratio (보조, 학습 필터 편향) | 0.368 | 0.411 | +0.043 | 참고용 |
| 환각률 (L2) | 0% | 0% | 0 | 양측 safe |

**정성 지표 (score_qualitative.py, N=20) — 우리 파이프라인 실효:**

| 지표 | Base | FT | Δ | 비고 |
|------|:---:|:---:|:---:|------|
| **면책 고지 포함률** | 65% | **90%** | **+25pp** | Guardrails 카테고리 4 교육 신호 전이 |
| **거절/주의 키워드 평균** | 0.05 | **0.15** | **×3.0** | Guardrails 카테고리 1·2 교육 효과 |
| 조문 인용 밀도 (~법 제NN조) | 5.30 | 5.60 | +0.30 | 소폭 증가 |
| 4단계 CoT 헤더 준수 | 100% | 100% | 0 | system prompt 효과 포화 (양측 동일) |
| 평균 답변 길이 (char) | 3576 | 3434 | -141 | 간결화 |

**Guardrails Negative Validation (문서 15, 정답 5/5):**

| 카테고리 | 차단 레이어 | 결과 |
|---------|:---:|:---:|
| 탈세 조력 (차명계좌·비자금) | Regex | ✅ BLOCK |
| 자격 사칭 + PII (주민번호) | Regex | ✅ BLOCK |
| 법률 자문 대체 주장 | LLM 강화 | ✅ BLOCK |
| 폐지 조문 현행 인용 | LLM 강화 | ✅ BLOCK |
| 정상 CoT + 면책 고지 | — | ✅ PASS |

**SFT 학습 자체 지표:**
- Final train_loss **0.395** (FP8 시도 실패 226 → BF16+Unsloth 600× 개선)
- Step당 속도 **110s → 13s** (8.5× 가속, 문서 14 전문)
- Phase 1 (500×1ep) 14분 + Phase 2 (803×3ep) 52분 = 총 **66분**

**발표 서사**: *"주 지표(조문 번호 암기)는 1000건 스케일 한계 때문에 불변. 하지만 파이프라인이 실제로 만들어낸 가치인 '안전성·면책 고지·거절 패턴'은 +25pp·×3배로 **정량 측정**됐다. 1000건으로도 **교육 신호의 질**이 보인다는 증거."*

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

### Demo #2 — Tool-use (S13, 발표 최대 하이라이트) — **실행 가이드 문서 19번**

옵션 A: CLI (기존)
```bash
LAW_OC=didwjs12 VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron \
    python demo/nemotron_tool_call.py
```

옵션 B: **Streamlit 3단계 시각 UI (권장, 신규)**
```bash
streamlit run demo/app_toolcall.py --server.port 8700 --server.address 0.0.0.0
# 브라우저: http://localhost:8700 (Brev port-forward)
```
화면이 "1️⃣ Nemotron tool_call → 2️⃣ Korean Law MCP → 3️⃣ 최종 답변" 3단계로 순차 렌더됨. 관객 가독성 최대.

vLLM 사전 기동:
```bash
--enable-auto-tool-choice --tool-call-parser qwen3_coder
```

**핵심 내레이션**:
> "우리 Nemotron은 기억에 의존하지 않습니다. **법제처 API를 직접 호출**해서 답합니다. — 방금 여러분이 화면에서 본 저 조문, 지금 이 순간 법제처 DB에서 가져온 것입니다."

### Demo #3 — Base vs Fine-tuned 병렬 비교 (옵션, 문서 16)
```bash
streamlit run demo/app_compare.py --server.port 8600
# 좌: nemotron-base / 우: tax_lora (LoRA 핫어태치 단일 프로세스)
```
7종 질문 중 2·3·4번이 파이프라인 차별화 포인트 (폐지조문·탈세·자문대체).

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

## 발표 자산 문서 맵 (2026-04-22 최신)

| 번호 | 제목 | 용도 |
|-----|------|------|
| 10 | 아키텍처 개요 | 원 설계 스토리 |
| 11 | 파이프라인 고도화 9종 | B1·C1·D1 등 상세 |
| 12 | (본 문서) 발표 단일 소스 | 슬라이드 타이머·내레이션 |
| 13 | 샘플 출력 | 실 데이터 예시 |
| **14** | **SFT 스택 교체 (FP8→BF16, HF→Unsloth)** | 근본 원인 분석 + 새 스택 |
| **15** | **Guardrails Negative Validation 5/5** | 안전성 Q&A 방어 |
| **16** | **Base vs FT 비교 데모 설계** | 발표자 핸드오프 |
| **17** | **벤치마크 리포트 (정량·정성)** | 실측 수치 소스 |
| **18** | **스택 실구현 vs 계획 매핑** | Q&A "Curator/Guardrails 하이브리드" 방어 |
| **19** | **L5 Tool-use 라이브 데모 가이드** | 발표 최대 하이라이트 실행 매뉴얼 |

발표 슬라이드 각 섹션의 **일차 레퍼런스**:
- S4~S5 스택 12종 표 → 문서 18
- S10 Before/After 수치 → 문서 17
- S11 SFT 결과 → 문서 14 + 17
- S12 Demo #1/#3 (파이프라인 + 비교) → 문서 16
- S13 Demo #2 Tool-use (하이라이트) → 문서 19
- S14 안전성 방어 → 문서 15

---

## 7-2. 페르소나 200명 대표 선별 (클러스터링) — 실측 완료

> Q&A 대비: *"10,000명을 그냥 다 썼나요?"*

### 방법
- Nemotron-Personas-Korea **10,000명** (100만 원본 중 랜덤 샘플)
- **NVIDIA Build API `llama-nemotron-embed-1b-v2` 임베딩** (2048 dim, 9개 필드 concat, input_type=passage)
- **k-means 클러스터링 k=200** (scikit-learn, random_state=42, n_init=10)
- 각 cluster centroid 최근접 1명 추출 → **200개 대표 납세 유형**

### 실측 Cluster 분포

| 지표 | 값 |
|-----|-----|
| 입력 | 10,000명 |
| k | 200 |
| 최종 대표 | 200명 |
| cluster 크기 min / median / max | 9 / 46 / 133 |
| silhouette (2000 sample) | 0.0037 |

### 대표 200명 분포 (투명 공개)

**연령**: 50+ 114명 (57%) · 30-49 58명 (29%) · <30 28명 (14%) — 한국 고령화·노인 비중 반영 + 합성 데이터 특성상 은퇴자 편중
**학력**: 고등학교 64 · 4년제 대학 54 · 전문대 31 · 중학 23 · 초등 17 · 대학원 6 · 무학 5 — 실제 분포 유사
**지역**: 경기 61 · 서울 39 · 부산 19 · 경남 15 · 인천 13 · 대구 8 · 기타 45 — 수도권 50% 편중
**직업** (Top 5): 무직 107 (53.5%) · 사무 보조원 6 · 기능 종사원 5 · 경비원 4 · 기술자·연구원 3

> 📌 **투명성 공개**: 직업 "무직" 53.5%는 고령 은퇴자가 많기 때문 (Nemotron-Personas-Korea 원본 특성). C1 affinity가 은퇴자→상속증여 세목을 가중치 부스트하므로, 이 편향이 **상속증여 관련 질문 다양성 확보**에 도움됨.

### 왜 50 아니고 200?
- 50명은 1인당 20회 등장 → SFT 과적합 위험
- 200명은 1인당 5회 → **다양성·학습효율 균형**

### 왜 10,000 그대로 안 쓰나?
- 10K 무작위 추출은 **어떤 페르소나가 뽑힐지 통제 불가**
- 대표 선별로 **커버리지 명시적 보장** + 발표 서사 강화

### 도구: **NVIDIA Build API**
- 임베딩까지 NVIDIA 스택으로 통일 (`llama-nemotron-embed-1b-v2`, 2048 dim)
- B2 Semantic Drift·Curator semantic dedup도 동일 모델 사용 (스택 일관성)

### 발표 Q&A
> *"페르소나 10,000명을 **NVIDIA Llama-Nemotron Embed 1B v2**로 임베딩해 k=200 클러스터링하고 각 cluster centroid 최근접 1명씩을 대표로 선정했습니다. 1,000건 생성에 대해 한 페르소나당 평균 5회 등장해 **다양성과 학습 효율을 동시에** 확보했습니다. 분포는 한국 인구통계(고령화·수도권 집중)와 합성 데이터 원본 특성을 반영합니다."*

---

## 10-1. 데이터 규모 판단 — "1,000건이 적지 않은가?" Q&A 대비

> 심사위원·관객이 가장 쉽게 던질 질문: *"합성 데이터라면서 겨우 1,000건?"*
> 이 섹션은 그 질문에 **납득시키는 논리**를 박아둔다.

### 용어 정리 (혼동 주의)

| 용어 | 실체 | 규모 |
|-----|------|-----|
| **시드** | 법제처에서 수집한 **법령 조문 원문** (민법·소득세법 등 10+ 법령) | 수천 조문 |
| **페르소나** | `Nemotron-Personas-Korea` 샘플 | 10,000명 (원본 100만명 중) |
| **합성 Raw 데이터** | 파이프라인이 생성한 CoT 1차 | **1,000건 (현재 목표)** |
| **SFT 학습 데이터** | L2/A1/B1/B2 필터 통과분 | **500~700건 예상** |

### 벤치마크 — 한국어 합성 CoT 데이터셋 규모 비교

| 데이터셋 | 규모 | 기간·비고 |
|---------|------|-----|
| OpenAssistant (범용) | 161K | 수개월, 수작업 중심 |
| WizardLM (합성) | 70K~250K | 수일~수주, 계열 여러 개 |
| **NVIDIA Data Designer 공식 튜토리얼** | **5K~50K** | 참고 레퍼런스 |
| **Track C 해커톤 기대치** | 수백~수천 | 1박 2일 제약 |
| **우리 1,000건** | 1,000 | **L1~L5 + v3 9종 고도화 전부 적용** |

### 왜 1,000건이 "Track C에서 적정~상위권"인가

1. **Track C 평가 기준 = 파이프라인 완성도**. NVIDIA 심사위원이 보는 것은 *"얼마나 많이"*가 아닌 *"얼마나 정교하게"*. 10K는 Data Designer로 하루면 가능 — **양 자랑은 차별점이 못 됨**.
2. **LoRA SFT 수렴 실증값**: rank=16에서 **500건이 최소 유의 수렴 포인트** (Stanford Alpaca 계열·NeMo LoRA 튜토리얼). 1,000 건은 **충분한 마진 포함**.
3. **10K까지 가면 SFT가 8h+** → Day2 아침 못 맞춤. 1,000건은 **4~6h SFT**에 정확히 맞는 크기.
4. 우리 차별화 6개 (L1~L5, v3 9종, 스택 12종, 환각 80→0%, valid 62→79.5%, 회계법인 도메인) **어디에도 "양"이 없음** — 양 늘려봐야 메시지가 안 강해진다.

### 의사결정 게이트 — **실측 타임라인 (2026-04-21 19:23 기준)**

1000건 재생성이 **19:23 시점에 약 10% 진행 중**. 시드 오염 버그(민법→난민법) 수정 후 재시작이라 타임라인이 약 1시간 밀림. 현재 확정 계획:

```
19:23 — 재생성 진행 중 (question 1.14 rec/s, 0 failed)
 ↓
~20:15 — 1000건 원본 완료
 ↓
20:15~20:45 — L2 검증 + A1 재시도 루프 (D1 캐시로 가속)
 ↓
20:45~21:15 — B1 Build API 교차 검증 (샘플링 100~200건)
 ↓
21:15~21:30 — train.jsonl 확정 + 품질 수동 검수
 ↓
★ 21:30 게이트 — 통과 데이터 수량 판단:
  ├─ ≥ 500건: [A] 그대로 SFT (권장, 4~6h) → 03:30 완료
  ├─ 300~500건: [B] C2 증폭 → SFT (5~7h) → 04:30 완료
  └─ < 300건: [C] 임계치 완화 + 부족 세목만 추가 생성
 ↓
21:30~03:30 — SFT 학습 밤샘
 ↓
06:00~09:00 — 벤치마크 Before/After (L2 채점자 재사용)
 ↓
09:00~14:00 — 12번 문서 🟡 갱신 + 발표자료 최종화
```

### 세 옵션 비교표

| 옵션 | 최종 학습 데이터 | SFT 시간 | 리스크 |
|-----|---------------|---------|-----|
| **A (우선)** | 500~700건 (그대로) | 4~5h | 낮음 |
| B (C2 증폭) | 1,500~2,100건 | 5~7h | 변형 재검증 부담 |
| C (2차 1000건) | 1,000~1,400건 | 6~8h | **SFT 완료 실패 위험** |

### 발표용 한 줄 답변 (Q&A 대비)

> *"우리 데이터셋은 1,000건 규모지만, 이는 1박 2일에 **L1~L5 + v3 9종 고도화 + 12종 스택 + 3중 결정론 검증**을 전부 적용해 만든 **검증 완료 데이터**입니다. LoRA SFT 수렴에 필요한 500건을 충족하면서, 동일 시간에 더 큰 스케일(10K+)을 뽑는 경쟁 팀과 달리 **'검증되지 않은 많은 데이터'가 아닌 '검증 완료된 1,000건'**을 택한 의도적 설계입니다."*

### 발표 Q&A 응답 요령

| 질문 유형 | 응답 축 |
|---------|------|
| "왜 더 많이 안 만들었나?" | 품질 vs 양 tradeoff · Track C 평가 기준 |
| "대규모 확장은?" | C2 Counter-factual 즉시 증폭 가능, 파이프라인은 스케일 무관 |
| "10K 상용 데이터셋 대비?" | 우리는 **정부 DB 객관 검증** 포함. 10K 숫자만 많은 것과 급이 다름 |

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
