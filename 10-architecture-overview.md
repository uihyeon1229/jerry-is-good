# 10. 아키텍처 Overview — 발표 PPT 초안

> **목적**: 팀 외부(심사위원·관객)에게 **한 번에 이해되는 큰 그림**. PPT 슬라이드로 그대로 옮겨도 되도록 섹션·수치·다이어그램을 슬라이드 단위로 구성. 구현 세부는 [09-pipeline-design-v2.md](./09-pipeline-design-v2.md) 참조.
>
> 작성: 2026-04-21 / 구현 진행 중 (수치는 실측·잠정 포함)

---

## Slide 1 — 타이틀

# 환각 없는 한국 법률 CoT 데이터 파이프라인
### *Nemotron-Personas × Nemotron × 법제처 MCP — NVIDIA 풀스택 9종 End-to-End*

- **NVIDIA Nemotron Hackathon Track C**: 합성 데이터 생성
- **팀**: 4인 (회계법인) — `jerryisgood`
- **기간**: 1박 2일 (약 30시간)
- **리포지토리**: https://github.com/uihyeon1229/jerry-is-good

---

## Slide 2 — 문제 제기

> **"한국 법률을 물으면 LLM은 조문을 지어낸다."**

### 실측 증거 (Nemotron 3 Nano FP8, 공식 가이드대로 생성)

| 세목 | 인용 조문 예시 | 실존 여부 |
|------|------|---------|
| 부가가치세-매입세액공제 | 부가가치세법 제118·119·122조 | ❌ 존재 범위는 ~제76조 |
| 법인세-세무조정 | 법인세법 제126조, 제41조의2 | ❌ 없음 |
| 소득세-고급 | (법령명 미지정) 제20·47조 | ⚠ 애매 |

### 5건 smoke test에서 측정
- **80% (4/5) 레코드에서 환각 감지**
- 평균 조문 인용 실존률 **35%**
- 수작업 어노테이션 비용 고려하면, 이 상태로는 **훈련용 데이터로 못 씀**

**→ 환각을 "사후 제거"가 아닌 "파이프라인 구조로 차단"해야 한다.**

---

## Slide 3 — 한 문장 솔루션

> **Nemotron-Personas로 질문을 만들고, Nemotron으로 답하고, 법제처 MCP로 검증하고, Nemotron을 파인튜닝해 실증한다.**

NVIDIA가 공개한 **한국어 페르소나 100만명** × 같은 **NVIDIA 모델** × **한국 법제처 공식 API** 가 하나의 파이프라인 안에서 맞물린다.

---

## Slide 4 — 5대 차별화 레버 (L1~L5)

| # | 레버 | 역할 | 우리가 해결한 것 |
|---|-----|------|---------------|
| **L1** | 법제처 조문을 프롬프트 Seed Context로 주입 | 환각 **사전 차단** | 세목별 실질 조문 화이트리스트 8개 도메인 |
| **L2** | Korean Law MCP `verify_citations` 결정론 검증 | 환각 **사후 제거** | MCP 17개 도구 중 `verify_citations` 배치 호출 |
| **L3** | 계산문제 수치를 sympy로 재계산 | 수치 **정답 보장** | 세법 계산문제만 적용 (민법·노동법 skip) |
| **L4** | Nemotron-Personas-Korea로 질문 다양성 | 데이터셋 **쓸모** ↑ | 100만명 중 10,000명 샘플링 + 조건부 난이도 매핑 |
| **L5** | Nemotron + MCP Tool-use 라이브 데모 | 발표 **임팩트** | vLLM `--enable-auto-tool-choice` 로 실시간 조문 조회 |

**+ 보너스**: Curator semantic dedup · Nsight GPU 프로파일 · SFT Before/After 벤치마크

---

## Slide 5 — NVIDIA 스택 9종 End-to-End

| # | 기술 | 역할 |
|---|------|------|
| 1 | **Brev.dev** | H100 80GB 프로비저닝 |
| 2 | **Nemotron 3 Nano 30B A3B FP8** | 데이터 생성 LLM (1x H100) |
| 3 | **vLLM + nano_v3 reasoning parser** | OpenAI 호환 서빙, thinking 분리 |
| 4 | **NeMo Data Designer** | 스키마 선언적 파이프라인 엔진 |
| 5 | **NeMo Curator** | 중복 제거 + 품질 필터 + semantic cluster 다양성 |
| 6 | **NeMo Guardrails** | 탈세 조력·PII·법률 자문 탈선 차단 |
| 7 | **NeMo Framework (SFT)** | 같은 Nemotron을 LoRA로 파인튜닝 |
| 8 | **NVIDIA Build API / Nsight** | 외부 교차 검증 + GPU 프로파일 증빙 |
| 9 | **Nemotron-Personas-Korea** | 한국어 페르소나 100만명 (질문 다양성 Seed) |

**+ 외부 통합**: **Korean Law MCP** (`chrisryugj/korean-law-mcp`) · **법제처 Open API** (공개 무료)

---

## Slide 6 — 아키텍처 다이어그램

```
                    ┌─────────────────────┐    ┌──────────────────────────┐
                    │  법제처 Open API     │    │  Nemotron-Personas-Korea │
                    │  (조문 · 판례 DB)    │    │  (HuggingFace · 100만명)  │
                    └─────────┬───────────┘    └────────────┬─────────────┘
                              │                             │
                              ▼                             ▼
                     ┌──────────────────┐         ┌──────────────────────┐
                     │  시드 수집 S0     │         │  페르소나 10K 샘플   │
                     │  scripts/        │         │  pipeline/           │
                     │   collect_seeds  │         │   fetch_personas     │
                     └────────┬─────────┘         └──────────┬───────────┘
                              │                              │
                              ▼                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    Brev H100 · vLLM Nemotron 3 Nano FP8                      │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  NeMo Data Designer (builder.py)                                    │    │
│   │                                                                     │    │
│   │   Sampler   │ 세목(8) × 질문유형(4) × 난이도(3) × 페르소나(index) │    │
│   │   Custom    │ seed_context  ← L1: 세목별 실질 조문 Top-N          │    │
│   │   LLMText   │ question      ← L4: 페르소나 주입                   │    │
│   │   LLMText   │ reasoning_cot ← L1: seed 목록만 인용 강제           │    │
│   │   LLMStruct │ metadata      ← TaxMetadata (applied_law_mst[] 등)  │    │
│   │   LLMJudge  │ quality_score ← 3축 (legal/cot/utility × 1-5)       │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│                       output/raw/*.jsonl  (예: 1000건)                       │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S2: Korean Law MCP `verify_citations` (L2)                         │    │
│   │    → valid_ratio, has_hallucination, invalid_refs 컬럼 주입         │    │
│   │    → valid_ratio < 0.7 또는 has_hallucination=True 제거             │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S3: Python/sympy 계산 검증 (L3, 세법 계산문제만)                   │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S4: NeMo Guardrails  (탈세/PII/법률 자문 대체 차단)                │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S5: NeMo Curator  (dedup + 품질 + semantic cluster 다양성)         │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  output/final/{train, eval}.jsonl  (ChatML 포맷 · 약 500건)         │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S6: NeMo Framework — Nemotron Nano FP8 + LoRA (r=16, α=32)         │    │
│   │      epoch 3, lr 1e-5, 배치 2 · grad accum 16                       │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S7: Benchmark Before/After (20문제) + Nsight GPU 프로파일           │    │
│   │      · 채점은 L2 citation_validator 재사용 (객관성)                  │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐    │
│   │  S8: 라이브 Tool-use 데모 — Nemotron이 MCP를 function-call로 호출    │    │
│   └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Slide 7 — 데이터 스키마 (3도메인 × 8세부)

### 도메인 축 4개 (Sampler)

| 축 | 값 | 비고 |
|---|---|-----|
| **세목** | 세법 4 (소득/법인/부가/상증) + 민법 2 (계약임대차/상속증여) + 노동법 2 (임금퇴직금/해고연차) | 총 **8세부** |
| **질문유형** | 계산문제 · 법령해석 · 사례적용 · 개념설명 | 4종 |
| **난이도** | 기초 · 중급 · 고급 | **페르소나 학력과 조건부 매핑** |
| **페르소나** | Nemotron-Personas-Korea index (10,000명) | age · occupation · education · family_type · region 등 10 필드 |

### 조건부 난이도 매핑 (페르소나 학력 → 난이도 가중치)

| education_level | 기초 | 중급 | 고급 |
|-----------------|------|------|------|
| 무학 | 0.85 | 0.14 | 0.01 |
| 초등학교 | 0.75 | 0.23 | 0.02 |
| 중학교 | 0.65 | 0.30 | 0.05 |
| 고등학교 | 0.45 | 0.45 | 0.10 |
| 2~3년제 전문대학 | 0.30 | 0.50 | 0.20 |
| 4년제 대학교 | 0.20 | 0.55 | 0.25 |
| 대학원 | 0.08 | 0.42 | 0.50 |

### 출력 컬럼

| 컬럼 | 타입 | 내용 |
|-----|------|-----|
| `question` | LLMText (페르소나 주입) | 납세자/실무자 관점 질문 |
| `seed_context` | Custom (L1) | 세목별 실질 조문 Top-N (예: 소득세 §20·§47·§51…) |
| `reasoning_cot` | LLMText (L1 강제) | **적용 조문 → 사실관계 → 해석/계산 → 결론** 4단계 |
| `metadata` | LLMStructured | `applied_law_mst[]`, `final_answer`, `concepts_used[]`, `num_reasoning_steps`, `requires_calculation`, `references_precedent` |
| `quality_score` | LLMJudge | `legal_accuracy`, `cot_depth`, `practical_utility` × 1-5 |
| `cited_laws_valid_ratio` | L2 주입 | MCP 검증 통과율 |
| `has_hallucination` | L2 주입 | `[HALLUCINATION_DETECTED]` 플래그 |
| `calc_verified` | L3 주입 | sympy 재계산 일치 여부 (세법 계산문제만) |

---

## Slide 8 — LIVE DEMO #1: 파이프라인 한 건 생성 (30초)

```bash
# 인스턴스 내부
cd /home/shadeform/jerry-is-good
source /home/shadeform/track3/bin/activate
python -m pipeline.run_generate --n 1 --mode preview
```

**화면에 보여줄 흐름**:
1. Sampler → (세법-소득세, 계산문제, 중급, 페르소나: 42세 교사)
2. seed_context 주입 → 소득세법 §20, §47, §51, §52, §24
3. question 생성 → "교사 A의 연봉 8천만원 상황에서 근로소득공제는?"
4. reasoning_cot 생성 (4단계 구조 출력)
5. MCP `verify_citations` → `✓ 소득세법 제47조 실존`
6. 최종 JSON 출력

---

## Slide 9 — 품질 지표 (실측 Before/After)

### 실측 스모크 테스트 (2026-04-21)

| 지표 | Before (L1 없음) | After v2.2 (L1 + 화이트리스트) | 개선 |
|-----|---------------|-----------|------|
| **환각 감지 비율** | 80% (4/5) | **33% (1/3)** | **-59%p** |
| **조문 인용 실존률 (valid_ratio)** | 35% | **75%** | **+114%** |
| fill_rate | 100% | 100% | 유지 |
| CoT 4단계 구조 준수 | 일부 | **전부** | — |
| thinking/content 분리 | 섞임 | **깔끔** (nano_v3 parser) | — |
| 법률 자문 아님 고지 | 없음 | **자동 삽입** | — |

> **이후 50건·1000건으로 스케일업하며 통계적 유의성 확보 예정.**

---

## Slide 10 — 3중 결정론 검증 (우리의 핵심 기술)

> "Judge **LLM 점수**가 아니라 **법제처 DB 매칭률**로 데이터 품질을 증명한다."

```
 ┌──────────────────────────────────────────────────────────────┐
 │  L1  Seed Context 주입  (사전 차단)                          │
 │     → 프롬프트 자체에 실존 조문 Top-N 박아넣음                │
 ├──────────────────────────────────────────────────────────────┤
 │  L2  Korean Law MCP verify_citations  (사후 제거)            │
 │     → 모든 인용 조문을 법제처 DB와 교차 검증                 │
 │     → has_hallucination=True 레코드 전부 제거                │
 ├──────────────────────────────────────────────────────────────┤
 │  L3  sympy 계산 재검증  (수치 보장, 세법 계산문제)           │
 │     → 답변 내부 수식 파싱 → 재계산 → ±5% 허용               │
 └──────────────────────────────────────────────────────────────┘
```

**다른 팀이 "Judge가 3.5점 줬어요" 라고 할 때, 우리는 "법제처에서 확인했어요" 라고 한다.**

---

## Slide 11 — LIVE DEMO #2: Tool-use (L5, 발표 최대 하이라이트)

vLLM에 `--enable-auto-tool-choice` + MCP `search_law` 함수 spec 등록:

```python
tools = [{
  "type": "function",
  "function": {
    "name": "search_korean_law",
    "description": "한국 법령 조문을 실시간으로 조회",
    "parameters": {"law_name": "string", "article_no": "integer"}
  }
}]
```

```
[사용자]  "소득세법 제47조(근로소득공제)의 정확한 내용을 알려줘"
[Nemotron] (tool_call 발생 → Korean Law MCP 호출)
          "법제처 조회 결과: 근로소득공제액은 연간 총급여액 구간별로...
           (실시간 조회된 공식 조문 텍스트 그대로 출력)"
```

> **Nemotron이 법제처 공식 DB를 실시간으로 읽는 것을 관객이 직접 본다.**

---

## Slide 12 — Before/After 벤치마크 (계획)

### 평가 세트
- 20문제 (세법 8 + 민법 6 + 노동법 6)
- 난이도 분포: 기초 6 / 중급 10 / 고급 4
- **정답 근거 조문을 사전 확정** (팀 C 담당자 실무 검수)

### 평가 축 (각 1-5점)
1. **legal_accuracy**: L2 citation_validator **재사용** (객관 채점)
2. **cot_depth**: Judge LLM
3. **practical_utility**: Judge LLM

### 예상 결과 (잠정)

```
      Base Nemotron    SFT'd Nemotron (LoRA)
─────────────────────────────────────────────
legal      2.8              4.3   (+53%)
cot        3.1              4.0   (+29%)
utility    3.0              3.9   (+30%)
```

- X축 3축 막대 그래프, Y축 점수 1~5
- 세목별 세부 차이도 함께 표시

---

## Slide 13 — NVIDIA 스택 9종 활용 회고 (1/2)

| 기술 | 역할 | 실측 효과 |
|-----|------|---------|
| **Brev.dev** | H100 30분 내 확보 | 세팅 시간 최소화 |
| **Nemotron 3 Nano 30B FP8** | 생성·학습 단일 모델 | GPU 31GB · 처리량 479 tok/s |
| **vLLM + nano_v3 parser** | thinking 분리 | CoT 4단계 구조 추출 |
| **NeMo Data Designer** | 스키마 선언 | 8세부 × 4질문 × 3난이도 조합 자동 |
| **Nemotron-Personas-Korea** | 질문 다양성 Seed | 100만명 → 1만명 샘플, 연령 19~99, 지역 17개 권역 커버 |

---

## Slide 14 — NVIDIA 스택 9종 활용 회고 (2/2)

| 기술 | 역할 | 실측 효과 |
|-----|------|---------|
| **NeMo Curator** | dedup + 품질 필터 | 노이즈 X% 제거 (예정) |
| **NeMo Guardrails** | 탈세·PII·법률 자문 탈선 차단 | N건 위험 표현 필터 |
| **NeMo Framework (SFT)** | Nemotron Nano LoRA 파인튜닝 | legal_accuracy +53% (목표) |
| **Nsight / Build API** | GPU 프로파일 증빙 + 외부 교차 검증 | GPU utilization 프로파일 제공 |

**+ Korean Law MCP**: 법제처 공식 API를 17개 도구로 래핑. 우리는 `verify_citations`(L2) + `search_law`(L5) 두 도구를 파이프라인에 통합.

---

## Slide 15 — 확장 가능성

### 도메인
- 지금: 세법 4 + 민법 2 + 노동법 2 = **3도메인 8세부**
- 확장: 형법 · 상법 · 행정법 · 공정거래법 등 — **Korean Law MCP가 17개 도메인 전부 커버하므로 시드 수집 + 화이트리스트만 추가하면 즉시 확장**

### 모델 규모
- 지금: Nemotron 3 Nano 30B FP8 (1x H100)
- 확장: Nemotron 3 Super 120B FP8 (2x H100) 으로 생성 → Nano로 distillation

### 공개
- HuggingFace Hub 데이터셋 등록 (MIT 또는 CC-BY)
- 파이프라인 코드 GitHub 공개 (이미 공개 저장소)
- Nemotron Nano 세법 특화 LoRA 체크포인트 배포

---

## Slide 16 — 팀 & Thanks

- **팀**: 4인 (회계법인) — A 인프라 / B 파이프라인 / C 도메인 / D 평가·발표
- **감사**: **NVIDIA · Brev.dev · Friendli AI · 대한민국 법제처**
- **리포**: https://github.com/uihyeon1229/jerry-is-good

---

## Slide 17 — Q&A (예상 5개)

| Q | A 요점 |
|---|------|
| Super 아닌 Nano를 쓴 이유? | 1x H100으로 생성·학습 모두 수용. 남은 GPU 시간을 SFT에 투자. "작은 모델로도" 증명이 Track C 가치. |
| MCP 없이도 가능한가? | 기술적으론 가능하나 **환각 검증이 주관적**으로 전락. MCP의 법제처 DB = 유일한 객관 정답지. |
| Judge LLM 점수가 아닌 이유? | LLM 판사는 LLM 출력을 채점 — 같은 편향. 우리는 **법제처 DB의 조문 실존 여부**를 기준 삼아 객관성 확보. |
| 회계법인이 민법·노동법을? | **세법이 출발점**. 같은 방법론(L1~L5)을 민법·노동법으로 확장해 **파이프라인의 일반화 능력** 증명. |
| SFT 효과의 신뢰성? | SFT 후 벤치마크 채점을 **L2 검증자가 수행** (동일 객관 기준). "Judge 점수"가 아닌 "법제처 매칭률"로 증명. |

---

## 부록 A — 디렉터리 레이아웃

```
jerry-is-good/
├── pipeline/               # DD 기반 파이프라인 공통 모듈
│   ├── settings · providers · schema · columns · builder · seeds · personas
│   ├── run_generate · run_verify_citations · run_calc_validate
│   ├── run_guardrails · run_curator
│   └── validators/{citation_validator, calc_validator}
├── scripts/                # 쉘 래퍼 + 시드 수집
│   ├── launch_vllm.sh · run_smoke.sh · run_generate_*.sh
│   ├── collect_seeds.py
│   └── smoke/ (01~04 단계별 스모크)
├── training/               # NeMo Framework SFT (LoRA)
├── benchmark/              # Before/After 20문제 채점
├── demo/                   # L5 tool-use 라이브 데모
├── cache/                  # 시드·페르소나 (gitignore)
├── output/                 # raw → verified → filtered → final (gitignore)
└── 00~10 *.md              # 전략·설계·체크리스트 문서
```

## 부록 B — 실행 순서 (Day1 → Day2)

```
Day1 09 ┬─ vLLM 기동 · MCP 연결성 확인 · 시드 수집 · 페르소나 샘플링
       │
Day1 13 ┼─ 파이프라인 스켈레톤 검증 (50건 드라이런)
       │
Day1 15 ┼─ 1000건 본 생성 (백그라운드) · 발표 초안 동시 작성
       │
Day1 20 ┼─ S2 citation → S3 calc → S4 guardrails → S5 curator 체인
       │
Day1 22 ┼─ SFT LoRA 학습 시작 (6h 밤샘)
       │
Day2 06 ┼─ SFT 완료 · 벤치마크 Before/After
       │
Day2 10 ┼─ Nsight 캡처 · 발표자료 통합 · L5 tool-use 데모 리허설
       │
Day2 14 └─ 발표
```

## 부록 C — 실측·잠정 수치의 출처

| 수치 | 출처 | 비고 |
|-----|-----|-----|
| 100만명 페르소나 | `nvidia/Nemotron-Personas-Korea` HF 메타데이터 | 실측 |
| Nemotron 30B FP8 GPU 31GB | vLLM 로그 "Model loading took 31.4 GiB" | 실측 |
| 처리량 479 tok/s | DD Model usage summary | 실측 |
| valid_ratio 35% → 75% | 5건 vs 3건 스모크, L2 검증 | 실측 (표본 작음, 50건·1000건으로 확장 예정) |
| 환각 80% → 33% | 동일 표본 | 실측 (잠정) |
| SFT 개선 +53% | 목표치 | 잠정 (SFT 후 확정) |

---

## Slide 요약 (10분 발표 기준)

| 시간 | 슬라이드 | 메시지 |
|-----|--------|------|
| 0:00 | S1 타이틀 | 주제 · 팀 |
| 0:30 | S2 문제 | LLM이 조문 지어냄 — 80% 환각 실측 |
| 1:30 | S3 솔루션 | 한 문장 서사 |
| 2:00 | S4 5레버 | L1~L5 표 |
| 3:00 | S5 NVIDIA 9종 | 스택 전체 표 |
| 4:00 | S6 아키텍처 | 다이어그램 한 장 |
| 5:00 | S8 LIVE DEMO #1 | 생성 1건 실시간 |
| 7:00 | S9 Before/After | 핵심 수치 차트 |
| 8:00 | S10 3중 검증 | 우리의 기술적 차별화 |
| 9:00 | S11 LIVE DEMO #2 | Tool-use (하이라이트) |
| 10:00 | S12 벤치마크 | SFT 효과 |
| 11:00 | S15 확장·S16 Thanks | 마무리 |
| 12:00 | Q&A | 5개 예상 |

---

**이 문서는 PPT 초안 재료로 그대로 사용 가능. 실측 수치는 작업 진행에 따라 업데이트 예정.**
