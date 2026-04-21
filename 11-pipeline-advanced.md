# 11. 파이프라인 고도화 (v3 확장) — 9종 Enhancement

> **목적**: v2.2의 "linear filter" 파이프라인을 **"Self-Improving · Cross-Validated · Resilient"** 파이프라인으로 격상. 09·10 문서의 5레버(L1~L5) **위에 얹는** 고도화 레이어 9종.
>
> 작성: 2026-04-21 / 구현 순서 확정

## 11.1 9종 고도화 한눈에

| # | 카테고리 | 이름 | 목적 | 예상 | 우선도 |
|---|---------|------|-----|-----|------|
| **A1** | 루프 | L2 재시도 루프 | 환각 2차 저감 | 90m | 🔥 필수 |
| **A2** | 루프 | Judge 기반 Selective Regen | CoT 품질 ↑ | 30m | 🔥 필수 |
| **B1** | 검증 | Build API 교차 검증 | NVIDIA 8번째 스택 실증 | 90m | 🔥 필수 |
| **B2** | 검증 | Semantic Drift Detection (bge-m3) | 주제 이탈 자동 탐지 | 60m | 💡 추가 |
| **C1** | 다양성 | Persona-Law Affinity Matching | 질문 현실감 | 90m | 🔥 필수 |
| **C2** | 다양성 | Counter-factual Variation | SFT 데이터 3~5x | 90m | 💡 추가 |
| **D1** | 효율 | MCP·조문 캐시 레이어 | 속도 3~5x | 30m | 🔥 필수 |
| **D3** | 효율 | 병렬/배치 튜닝 | 속도 2x | 30m | 🔥 필수 |
| **D4** | 복구 | Checkpoint & Resume | 밤샘 중단 복구 | 90m | 🔥 필수 |

합계 **필수 6h + 추가 3h = 9h**. B 담당 혼자 Day1 13~22시에 커버 가능.

## 11.2 구현 순서 (Day1 오후 ~ 저녁)

```
13:00 ┬─ [D1] Cache Layer                       (30m · 속도 기반 확보)
      │
13:30 ┼─ [D3] Parallel Tuning                    (30m · 2x 가속)
      │
14:00 ┼─ [A1] L2 재시도 루프                      (90m · 환각 2차 저감)
      │
15:30 ┼─ [A2] Judge 기반 Regen                   (30m · A1 재사용)
      │
16:00 ┼─ [C1] Persona-Law Affinity               (90m · 페르소나 극대 활용)
      │
17:30 ┼─ [B1] Build API Cross-Verify             (90m · 8번째 스택 실증)
      │
19:00 ┼─ [D4] Checkpoint & Resume                (90m · 밤샘 복구)
      │
20:30 ┼─ [B2] Semantic Drift (bge-m3)            (60m · 품질 보강)
      │
21:30 ┼─ [C2] Counter-factual Variation          (90m · 3~5x 데이터)
      │
23:00 └─ 1000건 본 생성 (배경) + SFT 준비
```

## 11.3 상세 설계

### A1 — L2 재시도 루프 (`pipeline/refine_loop.py`)

**목적**: `has_hallucination=True` 또는 `valid_ratio < 0.7` 시 **같은 세목/질문** 재생성.

```python
# pipeline/refine_loop.py
MAX_RETRIES = 3
VALIDITY_THRESHOLD = 0.7


async def generate_with_retry(
    row: dict,
    mcp_session: ClientSession,
    retry_prompt_adjuster=None,
) -> dict:
    best = None
    for attempt in range(MAX_RETRIES):
        # row에 attempt 정보 주입 (선택)
        row_now = {**row, "_attempt": attempt}

        # 1) DD로 reasoning_cot 생성
        cot = await llm_generate_cot(row_now)
        row_now["reasoning_cot"] = cot

        # 2) L2 즉시 검증
        cit = await verify_text(mcp_session, cot)
        row_now.update(cit.to_dict())
        row_now["_attempts"] = attempt + 1

        if not cit.has_hallucination and cit.valid_ratio >= VALIDITY_THRESHOLD:
            return row_now  # 통과

        if best is None or cit.valid_ratio > best["cited_laws_valid_ratio"]:
            best = row_now

        # 3) 재시도 전 프롬프트 조정: 실패 조문 블랙리스트
        if cit.invalid_refs:
            row["seed_context"] = (
                row.get("seed_context", "")
                + "\n\n**이전 답변에서 다음 조문이 검증 실패 — 절대 재사용 금지: "
                + ", ".join(cit.invalid_refs) + "**"
            )

    best["_retry_max_reached"] = True
    return best
```

**출력 KPI 추가 컬럼**:
- `_attempts`: 성공까지 걸린 시도 횟수 (1~3)
- `_retry_max_reached`: 최종 실패여도 best 보존

**발표 수치 예상**:
- 1회차 통과율 67% → 3회 루프 후 **최종 통과율 90%+**

### A2 — Judge 기반 Selective Regen (`pipeline/refine_loop.py` 확장)

루프 조건에 Judge `cot_depth < 3` 추가. A1 인프라 그대로 재사용.

```python
def _needs_retry(row) -> bool:
    if row.get("has_hallucination"):
        return True
    if row.get("cited_laws_valid_ratio", 1.0) < VALIDITY_THRESHOLD:
        return True
    judge = row.get("quality_score") or {}
    if judge.get("cot_depth", 5) < 3:
        return True
    return False
```

### B1 — Build API 교차 검증 (`pipeline/validators/build_api_cross.py`)

**목적**: 같은 질문을 **NVIDIA Build API의 Nemotron Super 120B**에 보내 답변 생성 → 조문 인용 **교집합 비율** 계산.

```python
# pipeline/validators/build_api_cross.py
import os
from openai import AsyncOpenAI

BUILD_API_URL = "https://integrate.api.nvidia.com/v1"
BUILD_API_KEY = os.getenv("NVIDIA_BUILD_API_KEY")
BUILD_MODEL = "nvidia/nemotron-3-super-120b-a12b-fp8"  # 또는 가용 모델명 확인


async def cross_verify(question: str, reasoning_cot: str) -> dict:
    """Build API로 같은 질문 재생성 → 조문 교집합 측정."""
    client = AsyncOpenAI(base_url=BUILD_API_URL, api_key=BUILD_API_KEY)
    resp = await client.chat.completions.create(
        model=BUILD_MODEL,
        messages=[{"role": "user", "content": question}],
        max_tokens=2048,
    )
    super_cot = resp.choices[0].message.content

    # 양쪽에서 조문 추출 (citation_validator의 regex 재사용)
    nano_laws = set(extract_law_refs(reasoning_cot))
    super_laws = set(extract_law_refs(super_cot))

    if not nano_laws or not super_laws:
        overlap = 0.0
    else:
        overlap = len(nano_laws & super_laws) / len(nano_laws | super_laws)

    return {
        "super_cot": super_cot[:500],
        "super_cited_refs": sorted(super_laws),
        "cross_overlap": overlap,
    }
```

**출력 컬럼**: `cross_overlap` (0~1, Nano와 Super의 조문 인용 교집합/합집합 비율)

**임계치**: `cross_overlap < 0.3` 이면 플래그 (둘 중 하나가 틀림, 수동 검수 대상)

**발표 서사**: *"우리는 Nemotron Nano가 인용한 조문을 Build API의 Super 120B로 교차 검증했다. 일치율 X%."*

### B2 — Semantic Drift Detection (`pipeline/validators/drift_detector.py`)

**목적**: `question` 임베딩 vs `reasoning_cot` 임베딩의 **코사인 유사도** 측정. 낮으면 답변이 주제 이탈.

```python
# pipeline/validators/drift_detector.py
from sentence_transformers import SentenceTransformer
_model = None

def _lazy_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-m3", device="cpu")
    return _model

def drift_score(question: str, cot: str) -> float:
    m = _lazy_model()
    q_emb, c_emb = m.encode([question, cot])
    sim = float((q_emb @ c_emb) / ((q_emb @ q_emb) ** 0.5 * (c_emb @ c_emb) ** 0.5))
    return sim
```

**출력 컬럼**: `qc_similarity` (0~1). `< 0.45` 이면 drop 대상.

### C1 — Persona-Law Affinity (`pipeline/personas.py` 확장)

페르소나의 `occupation` / `age` / `family_type` / `province` 를 **세목 가중치**로 매핑:

```python
# pipeline/personas.py 추가
SEMOK_BY_PERSONA = {
    # 나이대
    "20대": {"노동법-임금퇴직금": 0.30, "노동법-해고연차": 0.25, ...},
    "30~40대": {"세법-소득세": 0.25, "민법-계약임대차": 0.20, ...},
    "50대+": {"세법-상속증여세": 0.25, "민법-상속증여": 0.25, ...},
}

OCCUPATION_BOOST = {
    "사업자|자영업자|대표": {"세법-법인세": +0.15, "세법-부가가치세": +0.15},
    "은퇴|무직": {"세법-상속증여세": +0.10, "민법-상속증여": +0.10},
    "근로자|직장인|사무원|청소원|경비원": {"노동법-임금퇴직금": +0.15, "노동법-해고연차": +0.10},
}

def affinity_weights(persona: dict) -> dict[str, float]:
    """페르소나 → 세목별 가중치 (합 1.0)"""
    age = persona.get("age") or 35
    age_key = "20대" if age < 30 else "30~40대" if age < 50 else "50대+"
    weights = dict(SEMOK_BY_PERSONA[age_key])
    occ = persona.get("occupation") or ""
    for pattern, boost in OCCUPATION_BOOST.items():
        if any(k in occ for k in pattern.split("|")):
            for k, v in boost.items():
                weights[k] = weights.get(k, 0) + v
    # normalize
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}
```

**통합 지점**: DD의 Sampler `세목`을 **페르소나 의존 conditional_params**로 변경. `SamplerColumnConfig.conditional_params` 사용.

### C2 — Counter-factual Variation (`pipeline/variation.py`)

**목적**: 통과한 레코드마다 **수치만 미세 변경**한 변형 N개 자동 생성.

```python
# pipeline/variation.py
NUMERIC_RE = re.compile(r"(\d[\d,]*)\s*(원|만원|억|천만원|%)")

def make_variations(row: dict, k: int = 3) -> list[dict]:
    """같은 구조의 변형 k개 반환 (수치만 변경)."""
    question = row["question"]
    # 수치 추출
    matches = list(NUMERIC_RE.finditer(question))
    if not matches:
        return []
    variations = []
    for i in range(k):
        new_q = question
        # 각 수치를 ±30% 범위에서 랜덤 변경
        for m in matches:
            num = int(m.group(1).replace(",", ""))
            new_num = int(num * random.uniform(0.7, 1.3))
            new_q = new_q.replace(m.group(0), f"{new_num:,}{m.group(2)}", 1)
        variations.append({
            **row,
            "question": new_q,
            "_source_uuid": row.get("uuid"),
            "_variation_idx": i,
        })
    return variations
```

**제약**: 계산문제 변형은 **정답도 재계산** 필요 → L3 calc_validator 재실행으로 보장.

### D1 — Cache Layer (`pipeline/cache.py`)

MCP `verify_citations` 결과는 **cot 해시 → 결과** 로 디스크 캐시 (JSON). 1000건 중복 cot 검증 시 10x 가속.

```python
# pipeline/cache.py
import hashlib, json
from pathlib import Path

CACHE_DIR = Path("cache/validators")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def get(tag: str, text: str) -> dict | None:
    path = CACHE_DIR / f"{tag}_{_key(text)}.json"
    return json.loads(path.read_text()) if path.exists() else None

def put(tag: str, text: str, result: dict) -> None:
    path = CACHE_DIR / f"{tag}_{_key(text)}.json"
    path.write_text(json.dumps(result, ensure_ascii=False))
```

`citation_validator.verify_text`를 `cache.get/put` 로 wrap.

### D3 — Parallel Tuning

`pipeline/settings.py` `max_parallel`을 4 → **8**로. 추가로 DD의 `ChatCompletionInferenceParams.max_parallel_requests=8`.

vLLM은 `--max-num-seqs 16` 으로 재기동 권장 (저쪽 팀 허락 시).

### D4 — Checkpoint & Resume (`pipeline/checkpoint.py`)

1000건 생성 시 **매 50건마다** `output/raw/<name>_ckpt.jsonl`에 append. 재시작 시 이미 생성된 uuid 스킵.

```python
# pipeline/checkpoint.py
def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {json.loads(l).get("_row_id") for l in f if l.strip()}

def append_record(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
```

`run_generate.py` 수정: `--resume` 플래그로 기존 체크포인트 로드.

## 11.4 KPI (v2.2 → v3 개선 목표)

| 지표 | v2.2 실측 | v3 목표 | 기여 고도화 |
|-----|---------|--------|----------|
| 환각 비율 | 33% | **< 10%** | A1 |
| valid_ratio | 75% | **> 90%** | A1 |
| CoT 4단계 준수 | 대부분 | **전부** | A2 |
| 질문 현실감 (페르소나 일치) | N/A | **> 85%** | C1 |
| cross_overlap (Super vs Nano) | N/A | **> 40%** | B1 |
| 생성 처리량 | 0.23 rec/s | **0.5 rec/s +** | D1, D3 |
| 밤샘 복구 가능성 | 불가 | **가능** | D4 |
| 주제 drift 비율 | 미측정 | **< 5%** | B2 |
| 최종 SFT 학습 데이터 건수 | 500 | **1500+ (변형 포함)** | C2 |

## 11.5 발표 서사 업데이트

- **v2.2**: "5레버 (L1~L5)"
- **v3**: "5레버 + **9종 고도화** (Self-Improving · Cross-Validated · Resilient)"

한 문장 요약:
> *"우리는 Nemotron이 지어낸 조문을 법제처로 잡고, 그래도 틀리면 다시 생성하고, 같은 모델의 큰 버전으로 교차 검증하며, 페르소나에 맞는 질문만 뽑고, 그 모든 과정을 중단 없이 돌린다."*

## 11.6 파일 추가/수정 맵

```
pipeline/
├── refine_loop.py            (신규 — A1/A2)
├── cache.py                  (신규 — D1)
├── checkpoint.py             (신규 — D4)
├── variation.py              (신규 — C2)
├── validators/
│   ├── citation_validator.py (수정 — D1 cache wrap)
│   ├── build_api_cross.py    (신규 — B1)
│   └── drift_detector.py     (신규 — B2)
├── personas.py               (수정 — C1 affinity_weights)
├── builder.py                (수정 — C1 conditional Sampler)
├── settings.py               (수정 — D3 max_parallel=8)
└── run_generate.py           (수정 — refine_loop + checkpoint + resume)
```

## 11.7 리스크·대응

| 리스크 | 대응 |
|-------|-----|
| A1 루프로 GPU 시간 폭증 (3x) | MAX_RETRIES=2로 축소, 임계치 완화 (0.7 → 0.6) |
| B1 Build API 크레딧 소진 | 1000건 중 샘플링 100건만 cross-verify, 나머진 skip |
| B2 bge-m3 CPU 느림 | 배치 인코딩 (batch_size=32), 또는 GPU 일시 사용 |
| C1 페르소나 매핑 잘못 → 이상한 분포 | affinity 적용 전/후 분포 히스토그램으로 비교 |
| C2 수치 변형으로 계산 불가 질문 발생 | L3 calc_validator 재실행, 실패 변형 drop |
| D4 체크포인트 파일 손상 | `_ckpt.jsonl.tmp` → atomic rename |

## 11.8 실행 체크리스트 (1시간 단위)

- [ ] D1 Cache Layer → `test_cache.py` unit
- [ ] D3 max_parallel=8 설정 + 5건 스모크로 속도 측정
- [ ] A1 refine_loop 구현 → 5건 스모크로 환각율 측정 (33% → ?%)
- [ ] A2 Judge 조건 추가 → 같은 5건으로 재측정
- [ ] C1 affinity_weights 구현 → 50건 샘플 분포 검증
- [ ] B1 Build API 연결 테스트 → 1건 cross-verify 성공 확인
- [ ] D4 체크포인트 → kill -9 테스트 후 resume 확인
- [ ] B2 drift_detector → 5건 측정 (0.6~0.8 범위 예상)
- [ ] C2 variation → 통과 5건 각 3변형 = 15건 생성
- [ ] 통합 1000건 본 생성 (A1+A2+B1+B2+C1+C2+D1+D3+D4 전부 활성)
- [ ] SFT 학습 시작
