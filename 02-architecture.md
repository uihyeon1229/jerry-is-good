# 2. 전체 아키텍처

## 2.1 컴포넌트 다이어그램

```
┌───────────────────────────────────────────────────────────────┐
│                      외부 데이터 소스                          │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ 법제처 Open API (국가법령정보센터)                        │ │
│  │   • 소득세법/법인세법/부가가치세법/상증세법 조문          │ │
│  │   • 조세심판원 결정례                                     │ │
│  │   • 국세청 해석례                                         │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────┬───────────────────────────────────┘
                            │ OC 인증키
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                Korean Law MCP (chrisryugj)                    │
│  • search_law / get_law_text / get_annexes                    │
│  • search_decisions (17개 도메인 통합)                         │
│  • chain_full_research (AI검색→법령→판례→해석)                │
│  • verify_citations (환각 검증)                                │
└───────────────────────────┬───────────────────────────────────┘
                            │ JSONL 캐시
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                  Brev.dev H100 인스턴스                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  vLLM Server (port 5000)                                │  │
│  │    • nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8          │  │
│  │    • OpenAI 호환 API                                     │  │
│  │    • reasoning-parser nano_v3 (thinking 분리)           │  │
│  │    • tool-call-parser qwen3_coder                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         ▲                                      │
│                         │ HTTP                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  NeMo Data Designer (Python SDK)                        │  │
│  │                                                         │  │
│  │  SamplerColumn (결정론적)                                │  │
│  │    ├ 세목 (categorical × 6)                             │  │
│  │    ├ 질문유형 (categorical × 4)                         │  │
│  │    └ 난이도 (categorical × 3)                           │  │
│  │                                                         │  │
│  │  LLMTextColumn                                          │  │
│  │    ├ applied_law_context (MCP에서 pull, Jinja)         │  │
│  │    ├ question (납세자 관점 질문 생성)                   │  │
│  │    └ reasoning_cot (조문→사실→계산→결론)                │  │
│  │                                                         │  │
│  │  LLMStructuredColumn                                    │  │
│  │    └ metadata {applied_law_mst, answer, concepts}       │  │
│  │                                                         │  │
│  │  LLMJudgeColumn                                         │  │
│  │    └ quality_score (3축 × 1-5)                          │  │
│  │                                                         │  │
│  │  ExpressionColumn                                       │  │
│  │    └ chat_formatted (ChatML)                            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  NeMo Guardrails                                        │  │
│  │    • 탈세 조력 표현 차단                                 │  │
│  │    • 세무사 자격 사칭 차단                              │  │
│  │    • PII (개인정보/법인명) 차단                         │  │
│  │    • 폐지 조문 인용 차단                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  NeMo Curator                                           │  │
│  │    • 문서 중복 제거 (exact + fuzzy)                      │  │
│  │    • 의미적 중복 제거 (semantic dedup)                  │  │
│  │    • 품질 필터 (길이/언어/heuristic)                    │  │
│  │    • PII 스캐너                                          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  MCP verify_citations (★ 최종 환각 검증)                │  │
│  │    • 모든 applied_law_mst를 법제처 DB와 대조            │  │
│  │    • 존재하지 않는 조문 자동 제거                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Final Dataset (JSONL + Parquet)                        │  │
│  │    • train.jsonl (ChatML, SFT용)                        │  │
│  │    • eval.jsonl (벤치마크)                              │  │
│  │    • full.parquet (메타데이터 포함, 분석용)             │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  NeMo Framework (SFT)                                   │  │
│  │    • 대상: Nemotron 3 Nano 30B FP8 (LoRA)                │  │
│  │    • 기법: LoRA (r=16, alpha=32)                        ���  │
│  │    • 학습 시간: 4~6시간 on 1x H100                      │  │
│  │    • 배치 크기: 2, grad accum 16                        │  │
│  │    • epoch: 3, lr: 1e-5                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Benchmark Runner                                       │  │
│  │    • 20문제 × (Base vs SFT'd Nemotron Nano)              │  │
│  │    • Judge: Nemotron 3 Nano (자체 평가)                 │  │
│  │    • 정답 교차검증: MCP search_law                       │  │
│  │    • Nsight: GPU 사용률 프로파일 캡처                    │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

## 2.2 데이터 흐름 요약

```
1. MCP에서 시드 조문/판례 수집 (JSONL 캐시)
      ↓
2. Sampler가 (세목, 질문유형, 난이도) 조합 생성
      ↓
3. applied_law_context: MCP에서 해당 세목 조문 N개 pull
      ↓
4. question: LLM이 조문 기반으로 질문 생성
      ↓
5. reasoning_cot: LLM이 조문 인용하며 단계별 추론
      ↓
6. metadata 추출 (구조화)
      ↓
7. Judge 3축 평가 (법령정확성, CoT깊이, 유용성)
      ↓
8. Guardrails 필터 (탈세 조력 등 차단)
      ↓
9. Curator 중복/품질 필터
      ↓
10. MCP verify_citations (환각 제거)
      ↓
11. 최종 데이터셋 → SFT 학습 → 벤치마크
```

## 2.3 포트 및 서비스

| 서비스 | 포트 | 설명 |
|--------|------|------|
| vLLM API | 5000 | OpenAI 호환, `nemotron` 모델명 |
| Data Designer | N/A | SDK (프로세스 내 실행) |
| Korean Law MCP | 3000 또는 원격 | `korean-law-mcp.fly.dev/mcp?oc=키` |
| Jupyter | 8888 | 개발용 (선택) |

## 2.4 모델 설정 (Nemotron Nano FP8)

```yaml
생성 모델 (problem/solution):
  temperature: 0.9 / 0.3
  top_p: 0.95 / 0.9
  max_tokens: 4096 / 2048
  enable_thinking: true  # reasoning 모드

구조화 모델:
  temperature: 0.1
  max_tokens: 512
  response_format: json

Judge 모델:
  temperature: 0.1
  max_tokens: 1024
  enable_thinking: false  # 빠른 평가
```

## 2.5 파일 시스템 레이아웃 (H100 인스턴스 내부)

```
/workspace/
├── track3/                       # Python venv
├── scripts/
│   ├── launch_nemotron_nano.sh   # vLLM 실행
│   └── collect_seeds.py          # MCP 시드 수집
├── cache/
│   ├── seeds/
│   │   ├── income_tax.jsonl
│   │   ├── corporate_tax.jsonl
│   │   ├── vat.jsonl
│   │   └── inheritance_tax.jsonl
│   └── decisions.jsonl
├── pipeline/
│   ├── config.py                 # Data Designer 스키마
│   ├── guardrails/               # Guardrails config
│   └── curator_config.yaml
├── output/
│   ├── raw/                      # Data Designer 원본
│   ├── filtered/                 # Guardrails/Curator 통과
│   ├── verified/                 # MCP verify 통과
│   ├── train.jsonl
│   ├── eval.jsonl
│   └── full.parquet
├── training/
│   ├── sft_nemotron_nano_lora.py
│   └── checkpoints/
└── benchmark/
    ├── questions.jsonl           # 20문제
    ├── answers_base.jsonl
    ├── answers_sft.jsonl
    └── report.md
```
