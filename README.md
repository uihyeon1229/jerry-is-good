# NVIDIA Nemotron 해커톤 Track C — 팀 브리핑

> **한국 세법 QA CoT 합성 데이터셋 생성 + NVIDIA NeMo 풀스택 활용**
>
> 최종 업데이트: 2026-04-21

## 📌 목차
1. [대회 개요](#1-대회-개요)
2. [우리 팀 전략](#2-우리-팀-전략)
3. [기술 스택](#3-기술-스택)
4. [전체 아키텍처](#4-전체-아키텍처)
5. [데이터 스키마 설계](#5-데이터-스키마-설계)
6. [4인 역할 분담](#6-4인-역할-분담)
7. [1박 2일 타임라인](#7-1박-2일-타임라인)
8. [대회 전 준비사항 (지금 당장)](#8-대회-전-준비사항-지금-당장)
9. [발표 메시지](#9-발표-메시지)
10. [참고 링크](#10-참고-링크)

---

## 1. 대회 개요

| 항목 | 내용 |
|------|------|
| **대회** | NVIDIA Nemotron 해커톤 **Track C — 합성 데이터 생성** |
| **기간** | 1박 2일 (약 30~36시간) |
| **팀 구성** | 4인 (회계법인) |
| **제공 자원** | Brev.dev $1000 크레딧 (H100 사용 가능), Friendli AI 크레딧 |
| **가이드** | https://nemotron-dev-materials-q9notf2ox.brevlab.com/ |
| **공식 문서** | https://nvidia-nemo.github.io/DataDesigner/latest/ |

### Track C가 요구하는 것
- Nemotron 3 + NeMo Data Designer를 활용한 합성 데이터 파이프라인
- 스키마 기반 선언적 데이터 생성
- LLM-as-a-Judge로 품질 평가

---

## 2. 우리 팀 전략

### 🎯 핵심 전략
> **"데이터 결과물 품질"보다 "NVIDIA 스택을 얼마나 잘 활용했는가"로 승부한다.**

1박 2일 짧은 기간에 데이터 품질 경쟁으로 남들과 차별화하기 어렵다. 주관사(NVIDIA)가 가장 보고 싶어하는 것은 **자기 기술의 End-to-End 활용 사례**이므로, 여기에 집중한다.

### 3대 차별화 축

#### ① NVIDIA 스택 **8종** End-to-End 통합
- 단일 기술 1~2개가 아니라, **생성→필터→학습→평가 풀루프**를 NVIDIA 스택만으로 완성
- 발표에서 "우리는 NVIDIA 생태계를 이렇게 썼다"를 메인 서사로

#### ② 한국 법제처 공식 API (Korean Law MCP) 통합
- `chrisryugj/korean-law-mcp` 활용
- LLM 환각을 **법제처 공식 조문으로 원천 차단**
- "환각 없는 법률 CoT 생성" 스토리 = 심사위원에게 강렬한 인상

#### ③ 회계법인 도메인 정체성
- 한국 세법 QA: 감사보다 **CoT 적합도가 높고, 심사위원 이해도도 높음**
- "세무사 시험 수준" 임팩트 있는 데모 가능

### 왜 세법인가? (감사 vs 세법)

| 관점 | 감사 | 세법 ✅ |
|------|------|--------|
| 공개 데이터 | 중 (KSA, DART) | **상** (국세청/법제처/판례) |
| 심사위원 이해도 | 낮음 (전문 용어) | **높음** (누구나 세금 경험) |
| CoT 적합성 | 중 (판단 위주) | **상** (조문→사실→계산→결론) |
| 검증 용이성 | 낮음 | **중~상** (계산 결과 확인) |

### 왜 Nano 30B FP8인가? (Super vs Nano)

| 변형 | 필요 GPU | Day1 세팅 시간 | 추천 |
|------|---------|---------------|------|
| Super 120B BF16 | 4x H100 | 오래 걸림 | ❌ |
| Super 120B FP8 | 2x H100 | 중 | △ |
| **Nano 30B FP8** | **1x H100** | **짧음** | **✅** |
| Nano 30B NVFP4 | 1x B200 | 중 | △ (B200 확보 시) |

→ **1장 H100**만으로 충분, 발표에서도 "효율성" 어필 가능.

---

## 3. 기술 스택

### 🔷 NVIDIA 스택 (8종)

| # | 기술 | 역할 |
|---|------|------|
| 1 | **Brev.dev** | H100 GPU 프로비저닝 (스폰서) |
| 2 | **Nemotron 3 Nano FP8** | 데이터 생성 LLM (1x H100) |
| 3 | **vLLM + Reasoning Parser** | OpenAI 호환 서빙, thinking 모드 |
| 4 | **NeMo Data Designer** | 스키마 기반 합성 파이프라인 |
| 5 | **NeMo Curator** | 중복제거 + 품질필터 + PII 제거 |
| 6 | **NeMo Guardrails** | 탈세 조력/법률 탈선 차단 |
| 7 | **NeMo Framework (SFT)** | 소형 모델 파인튜닝 |
| 8 | **NVIDIA Build API / Nsight** | 비교 검증 + GPU 프로파일 증빙 |

### 🔶 외부 통합

| 기술 | 역할 |
|------|------|
| **Korean Law MCP** (`chrisryugj/korean-law-mcp`) | 법제처 공식 조문/판례 조회 + `verify_citations` 환각 검증 |
| **법제처 Open API** | MCP 데이터 소스 (무료 OC 키 1분 발급) |
| **Qwen2.5-1.5B** | SFT 대상 모델 (한국어 OK, 학습 4~6시간) |

---

## 4. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│ Day1 오전: 시드 확보                                    │
│                                                         │
│  Korean Law MCP                                         │
│    ├ search_law / get_law_text  → 조문 300~500개       │
│    └ search_decisions           → 판례·해석례 200개     │
│                                  ↓ JSONL 캐시           │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Day1 오후: 데이터 생성 파이프라인                       │
│                                                         │
│  Brev H100 → vLLM + Nemotron 3 Nano FP8                │
│                                                         │
│  NeMo Data Designer                                     │
│    ├ SamplerColumn    (세목 × 질문유형 × 난이도)       │
│    ├ LLMTextColumn    (question, MCP 조문 주입)        │
│    ├ LLMTextColumn    (CoT 풀이, 조문 인용)            │
│    ├ LLMStructuredColumn (applied_law_mst, answer)    │
│    └ LLMJudgeColumn   (법령정확성 × CoT깊이 × 유용성)  │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Day1 저녁: 필터링                                       │
│                                                         │
│  NeMo Guardrails  (탈세 조력 / PII 차단)               │
│    → NeMo Curator (중복제거 + 품질필터)                 │
│    → MCP verify_citations (★ 최종 환각 검증)           │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Day1 밤 ~ Day2 새벽: 학습 (백그라운드)                  │
│                                                         │
│  NeMo Framework SFT                                     │
│    대상: Qwen2.5-1.5B (LoRA)                            │
│    입력: ChatML messages                                │
│    학습 시간: 4~6시간                                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ Day2 오전: 평가                                         │
│                                                         │
│  Before/After 벤치마크 (20문제)                         │
│    → MCP로 정답 교차검증                                │
│    → Nsight GPU 프로파일 캡처                           │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 데이터 스키마 설계

### 대상 세목 (4개)

| 세목 | 하위 분류 | 비중 |
|------|----------|------|
| **소득세** | 근로소득, 사업소득 | 30% |
| **상속·증여세** | 상속공제, 증여재산가액 | 20% |
| **법인세** | 세무조정, 감가상각 | 25% |
| **부가가치세** | 과세·면세, 매입세액공제 | 25% |

### Sampler 축 (결정론적 분포)

```python
# 세목
세목 = ["소득세-근로", "소득세-사업", "상속세", "증여세",
        "법인세", "부가가치세"]

# 질문유형
질문유형 = ["계산문제", "법령해석", "사례적용", "개념설명"]

# 난이도
난이도 = ["기초(신고실무)", "중급(공제·감면)", "고급(세무조정·쟁점)"]
```

### LLM 컬럼

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `applied_law_context` | MCP Pull | 해당 세목 관련 조문 (Jinja context) |
| `question` | LLMTextColumn | 납세자/실무자 관점 질문 생성 |
| `reasoning_cot` | LLMTextColumn | 적용조문 → 사실관계 → 계산/해석 → 결론 |
| `metadata` | LLMStructuredColumn | `{applied_law_mst, final_answer, concepts[]}` |
| `quality_score` | LLMJudgeColumn | 법령정확성 / CoT깊이 / 실무유용성 (각 1-5) |
| `chat_formatted` | ExpressionColumn | SFT용 ChatML 형식 |

### Judge 루브릭 (3축)

1. **법령정확성 (1-5)**
   - 5점: 조문 번호·내용 모두 정확, 개정 반영
   - 3점: 방향은 맞으나 조문 번호 애매
   - 1점: 잘못된 조문 인용

2. **CoT 깊이 (1-5)**
   - 5점: 조문→사실→계산→결론 4단계 명확
   - 3점: 단계는 있으나 설명 얕음
   - 1점: 답만 있고 추론 과정 없음

3. **실무 유용성 (1-5)**
   - 5점: 실제 납세자/실무자가 바로 적용 가능
   - 3점: 맞지만 너무 교과서적
   - 1점: 추상적, 현실 괴리

### Guardrails 규칙

- ❌ 세무사 자격 사칭 표현
- ❌ 탈세 조력 (절세 vs 탈세 구분)
- ❌ 구체적 개인정보/법인명 생성
- ❌ 폐지된 조문 인용 (시드에 "2024년 기준" 명시)

---

## 6. 4인 역할 분담

| 역할 | Day1 | Day2 | 필요 역량 |
|------|------|------|---------|
| **A. 인프라/서빙** | Brev H100, vLLM + Nemotron 기동, SFT 실행 | Nsight 캡처, 모델 배포 | GPU·리눅스 능숙 |
| **B. 파이프라인** | Data Designer 스키마, Curator/Guardrails 통합 | 필터링 튜닝 | Python·ML 경험 |
| **C. 도메인/시드** | MCP 시드 수집, Judge 루브릭, 품질 검수 | 생성물 큐레이션 | **세무 실무자 필수** |
| **D. 평가/발표** | 벤치마크 20문제 구성, 발표 틀 | Before/After 비교, 발표자료 | 스토리텔링 |

> **현재 담당 미정 — 팀원 배정 필요**

---

## 7. 1박 2일 타임라인

### Day 1

| 시간 | 작업 | 담당 |
|------|------|------|
| 09:00–12:00 | Brev+vLLM 기동 / Data Designer 스캐폴딩 / MCP 시드 수집 / 벤치마크 설계 | 병렬 (A/B/C/D) |
| 12:00–14:00 | 점심 + 첫 통합 (Sampler→LLMText 5건 미리보기) | 전원 |
| 14:00–18:00 | 본 파이프라인 완성 + Curator/Guardrails/MCP verify 연결 | 전원 |
| 18:00–22:00 | **500~1000건 본 생성** (백그라운드) + 품질 검수 / 발표 초안 | 전원 |
| 22:00–       | **SFT 학습 시작** (Qwen2.5-1.5B, 백그라운드 밤샘) | A |

### Day 2

| 시간 | 작업 |
|------|------|
| 06:00–09:00 | SFT 완료 확인 → Before/After 벤치마크 실행 |
| 09:00–12:00 | 결과 분석, 실패 사례 개선, 발표용 하이라이트 10건 큐레이션 |
| 12:00–14:00 | 발표자료 최종화 (NVIDIA 스택 8종 활용 명시) |
| 14:00–       | 리허설 → 발표 → 제출 |

---

## 8. 대회 전 준비사항 (지금 당장)

> **대회 시작 전에 마쳐두면 Day1이 훨씬 편해집니다.** 팀원 아무나 가능.

### ✅ 체크리스트

#### [1] 법제처 Open API 키 발급 (1분, 무료)
- **누가**: 누구든 1명 (C 담당이 이상적)
- **어디서**: https://open.law.go.kr/LSO/openApi/guideList.do
- **결과물**: `OC` 키 (예: `honggildong`)
- **주의**: 발급받은 키는 팀 공용으로 공유

#### [2] Brev.dev 계정 가입 + 크레딧 확인 (5분)
- **누가**: A 담당
- **어디서**: https://brev.dev
- **확인사항**:
  - [ ] 스폰서 크레딧 $1000 연동 완료
  - [ ] H100 인스턴스 생성 절차 숙지
  - [ ] SSH 접속 및 key 세팅

#### [3] Korean Law MCP 로컬 테스트 (10분)
- **누가**: B 또는 C 담당
- **어디서**: 본인 로컬 PC (Mac/Windows/Linux)
- **명령**:
  ```bash
  # Windows PowerShell
  $env:LAW_OC="발급받은키"
  npx korean-law-mcp "소득세법 제20조"

  # Mac/Linux
  export LAW_OC=발급받은키
  npx korean-law-mcp "소득세법 제20조"
  ```
- **성공 기준**: 소득세법 제20조 조문 텍스트가 출력되면 OK

#### [4] HuggingFace 계정 + 토큰 발급 (5분)
- **누가**: A 담당
- **어디서**: https://huggingface.co/settings/tokens
- **목적**: Nemotron 3 Nano 모델 다운로드 + Qwen2.5-1.5B 다운로드
- **권한**: Read 권한으로 충분

#### [5] 팀 공용 저장소 준비 (5분)
- **누가**: 아무나
- **어디**: Git repo 또는 공유 드라이브
- **내용**:
  - 이 README
  - 생성될 시드 JSONL
  - 벤치마크 20문제 초안
  - 발표자료 초안

---

### 🎯 역할별 사전 학습 권장 (선택사항)

| 역할 | 읽어둘 것 |
|------|----------|
| A | [vLLM 문서](https://docs.vllm.ai), [Nemotron 3 Nano 카드](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8) |
| B | [NeMo Data Designer 문서](https://nvidia-nemo.github.io/DataDesigner/latest/), [NeMo Curator 문서](https://docs.nvidia.com) |
| C | [Korean Law MCP GitHub](https://github.com/chrisryugj/korean-law-mcp), 국세법령정보시스템 사용법 |
| D | 세목별 주요 쟁점 10개씩 미리 노트 |

---

## 9. 발표 메시지

### 🎤 One-liner (발표 첫 문장)
> "한국 법제처 Open API와 NVIDIA NeMo 풀스택을 통합하여, **환각 없는** 한국 세법 Chain-of-Thought 데이터셋을 생성하고, 생성한 데이터로 실제 모델을 파인튜닝한 End-to-End 파이프라인입니다."

### 🏆 심사위원 어필 포인트

| 사용 기술 | 발표 멘트 |
|---------|----------|
| **Nemotron 3 Nano FP8** | "1x H100으로 Nano 30B FP8 구동, 120B급 품질을 비용 효율적으로 실증" |
| **Reasoning Parser** | "thinking 토큰을 분리해 CoT 품질 가시화" |
| **Data Designer** | "스키마 선언만으로 세목 × 질문유형 × 난이도 × N 조합 자동 생성" |
| **NeMo Curator** | "의미적 중복 X%, 저품질 Y% 제거" (수치 제시) |
| **NeMo Guardrails** | "탈세 조력 표현 Z건 자동 차단" |
| **NeMo Framework SFT** | "Qwen2.5-1.5B Before/After 벤치마크 점수 N% 상승" |
| **Brev.dev** | "30분만에 H100 세팅 완료, 크레딧 효율 최적화" |
| **Korean Law MCP** | "법제처 공식 조문 기반, verify_citations로 환각 사전 차단" |

### 📊 발표 구조 (10~15분 기준)

1. **문제 제기** (1분) — 한국어 법률 CoT 데이터 희소, LLM 환각 위험
2. **솔루션** (1분) — NVIDIA 스택 + 법제처 API 통합
3. **아키텍처** (2분) — 위의 아키텍처 다이어그램 한 장
4. **라이브 데모** (3분) — 생성 샘플 3개 + SFT Before/After
5. **품질 지표** (2분) — Judge 점수, Curator 필터링율, 벤치마크
6. **NVIDIA 스택 8종 회고** (3분) — 각 기술별 "썼다/왜/효과"
7. **확장 가능성** (1분) — 다른 법 영역, 다국어, 더 큰 모델
8. **Q&A** (2분)

---

## 10. 참고 링크

### NVIDIA 공식
- [NeMo Data Designer 문서](https://nvidia-nemo.github.io/DataDesigner/latest/)
- [NeMo Data Designer GitHub](https://github.com/NVIDIA-NeMo/DataDesigner)
- [vLLM 문서](https://docs.vllm.ai)
- [Nemotron 3 Nano FP8 모델 카드](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8)
- [Nemotron 3 Super FP8 모델 카드](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8)
- [NVIDIA Build API](https://build.nvidia.com)

### 외부 통합
- [Korean Law MCP GitHub](https://github.com/chrisryugj/korean-law-mcp)
- [법제처 Open API 신청](https://open.law.go.kr/LSO/openApi/guideList.do)
- [국세법령정보시스템](https://txsi.hometax.go.kr/)
- [조세심판원 결정례](https://www.tt.go.kr/)

### 해커톤 자료
- [대회 가이드 페이지](https://nemotron-dev-materials-q9notf2ox.brevlab.com/)

---

## 📎 부록

### A. 왜 SFT까지 가는가?

**데이터 생성만 하면 "그래서?"** 라는 질문을 피할 수 없다. SFT Before/After 벤치마크를 보여주면:

1. **데이터 품질의 객관적 증명** — "우리 데이터로 학습하면 모델이 실제로 좋아진다"
2. **End-to-End 완결성** — NVIDIA 스택 풀루프 증명 (NeMo Framework 추가)
3. **시각적 임팩트** — 점수 차트 하나로 성과 어필

리스크: SFT 실패 시 발표 구성 깨짐 → **A 담당자 전담 + 백업 플랜 (발표에서 "시도했으나 시간 부족" 솔직히 언급)**.

### B. 1박 2일에 현실적인가?

| 작업 | 예상 시간 | 여유 |
|------|----------|------|
| Brev + vLLM 세팅 | 2시간 | 🟢 |
| MCP 시드 수집 | 2시간 | 🟢 |
| Data Designer 스키마 | 3시간 | 🟢 |
| 파이프라인 통합 | 4시간 | 🟡 |
| 500~1000건 생성 | 4시간 (백그라운드) | 🟢 |
| Guardrails/Curator/MCP verify | 2시간 | 🟡 |
| SFT 학습 | 6시간 (백그라운드) | 🟢 |
| 벤치마크 실행 | 2시간 | 🟢 |
| 발표자료 | 4시간 | 🟡 |
| **합계 (순차)** | **29시간** | — |
| **실제 (병렬 활용)** | **~24시간** | **🟢 여유 있음** |

### C. 만약 시간이 남으면

- Multi-turn 대화 형식 데이터 추가 (납세자 ↔ 세무 상담)
- RAPIDS/cuDF로 대규모 후처리 GPU 가속
- Guardrails에 PII 스캐너 연결
- HuggingFace Hub 공개 데이터셋 등록

### D. 만약 시간이 모자라면 (우선순위 하위)

- ❌ SFT 건너뛰고 "생성만" 완수 → 발표 임팩트↓
- ❌ Guardrails 간소화 (정규식 블랙리스트로 대체)
- ❌ 4개 세목 → 2개 세목(소득세, 법인세)으로 축소

---

**문의/수정**: 이 문서는 팀원 모두가 자유롭게 수정할 수 있습니다. 전략 변경 시 이 파일 업데이트 후 팀 공지.
