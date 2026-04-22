# 19 — L5 Tool-use 라이브 데모 실행 가이드

> **목적**: 원래 계획(`10-architecture-overview.md` §L5, Slide 12) 의 핵심 임팩트 —
> "**Nemotron이 법제처 공식 DB를 실시간으로 조회하는 것을 관객이 직접 본다**"
> 를 발표장에서 라이브로 재현하기 위한 실행 가이드.

---

## 1. 구조 한눈에

```
 사용자 질문 ───► Nemotron 3 Nano (vLLM, --enable-auto-tool-choice)
                       │
                       │ 1) tool_call 결정
                       │    { name: "search_korean_law",
                       │      args: { law_name: "소득세법", article_no: "47" } }
                       ▼
          우리 코드(demo/*) ──► Korean Law MCP (https://korean-law-mcp.fly.dev)
                                    │
                                    │ 2) search_law → MST 획득
                                    │ 3) get_law_text(MST, 제47조)
                                    ▼
                              법제처 Open API (공식) ── 조문 전문 반환
                       ◄───────────────────────────────────┘
                       │
                       │ 4) Nemotron 2차 호출 — 조문 원문 첨부
                       ▼
                    최종 자연어 답변 (조문 인용)
```

**발표 메시지**: *"기억에 의존한 답변이 아니라, 지금 이 순간 법제처에서 실제로 읽어온 조문을 근거로 답한다."*

---

## 2. 사전 조건

### 2.1 vLLM 기동 (Tool-use용)
기존 `vllm_demo`(LoRA 핫어태치) 또는 `vllm_gen`(base only) 과 **다른 설정** 필요. Tool-call 파서·reasoning 파서 옵션 포함해야 함.

```bash
# 기존 세션 종료 후
tmux kill-session -t vllm_demo 2>/dev/null
tmux kill-session -t vllm_gen 2>/dev/null

# Tool-use 전용 세션 (단일 모델, LoRA 없이)
tmux new -d -s vllm_tool 'source /home/shadeform/track3/bin/activate && \
  python -m vllm.entrypoints.openai.api_server \
    --model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --served-model-name nemotron \
    --host 0.0.0.0 --port 5000 \
    --max-model-len 8192 \
    --trust-remote-code \
    --gpu-memory-utilization 0.92 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    2>&1 | tee /ephemeral/training_logs/vllm_tool.log'
```

- `--tool-call-parser qwen3_coder` : Nemotron-H 계열이 Qwen-코더 호환 tool-call 포맷을 사용 (2026-04-21 공유 vLLM 실측)
- `reasoning-parser`(`nano_v3`)은 플러그인 파일이 있을 때만 옵션. 없어도 tool-use는 동작 (reasoning trace만 raw로 반환)

health check:
```bash
curl -s http://localhost:5000/v1/models | jq '.data[].id'    # nemotron
```

### 2.2 Korean Law MCP 연결성
```bash
LAW_OC=didwjs12
# Python으로 간단 ping
python - <<'PY'
import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def main():
    async with streamablehttp_client(f"https://korean-law-mcp.fly.dev/mcp?oc={LAW_OC}") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print([t.name for t in tools.tools][:10])

asyncio.run(main())
PY
```

17개 tool 중 본 데모는 `search_law`, `get_law_text` 둘만 사용.

---

## 3. 실행 옵션

### 3.1 옵션 A — CLI (기존 구현, 단순)
```bash
LAW_OC=didwjs12 VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron \
    python demo/nemotron_tool_call.py
```
출력: 2단 turn trace (1차 tool_call → MCP 호출 로그 → 2차 최종 답변).

### 3.2 옵션 B — Streamlit UI (발표용, 권장)
```bash
pip install streamlit openai mcp
LAW_OC=didwjs12 VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron \
    streamlit run demo/app_toolcall.py --server.port 8700 --server.address 0.0.0.0

# 로컬 포워딩
brev port-forward jerryisgood-h100-80gib-vram-sxm5 -p 8700:8700
# 브라우저: http://localhost:8700
```

UI 렌더링:
1. **단계 1**: Nemotron 1차 응답 + tool_call JSON 표시
2. **단계 2**: Korean Law MCP에서 조회된 조문 전문
3. **단계 3**: Nemotron 2차 최종 답변 (조문 인용)

발표 녹화 시 각 단계가 순차적으로 화면에 뜨는 것이 시각적으로 강렬.

---

## 3-A. 🔥 Smoke Test 실행 완료 (2026-04-22 10:59 KST)

4건 질문 전부 **end-to-end 성공**. 전체 trace: `artifacts/toolcall_smoke_log.md` (234 라인).

| # | 질문 | tool_call | MCP 응답 | 최종 답변 |
|---|------|:---:|:---:|:---:|
| 1 | "소득세법 제47조의 근로소득공제 내용을 알려주세요." | ✅ `search_korean_law(law_name='소득세법', article_no='47')` | ✅ 제47조 전문 | ✅ 5개 항목 구조화 요약 |
| 2 | "민법 제1000조는 상속 순위를 어떻게 정하고 있나요?" | ✅ | ✅ | ✅ |
| 3 | "근로기준법 제60조에 따라 3년 근속자의 연차유급휴가는 몇 일인가요?" | ✅ | ✅ | ✅ |
| 4 | "부가가치세법 제26조 제1항 면세 대상 재화·용역" | ✅ | ✅ | ✅ "제2항 부수재화" 추가 언급 |

**실행 환경 확정**:
- vLLM: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` + `--enable-auto-tool-choice --tool-call-parser qwen3_coder`
- tmux 세션: `vllm_tool`, port 5000
- 서빙 모델 이름: `nemotron`
- Korean Law MCP: `https://korean-law-mcp.fly.dev/mcp?oc=didwjs12` — 안정 응답 확인

**발표 임팩트 보장**: 최소 이 4개 질문은 발표장에서 라이브로 가도 성공 확률 매우 높음.

**녹화 전략**:
- VM은 headless 서버 → 영상 mp4 제작 불가
- 대체 자료 이미 확보:
  - `artifacts/toolcall_smoke_log.md` — 전체 2-turn trace (tool_call JSON + MCP 응답 + 최종 답변)
  - 발표자는 이 로그를 슬라이드 텍스트로 복사하거나, **Streamlit UI를 로컬 브라우저에 띄워 OBS/Windows Win+G 로 직접 녹화** 권장
  - 실제 mp4는 발표자 PC에서 생성

---

## 4. 시연 질문 세트 (검증된 후보)

| # | 질문 | 기대 tool_call | 기대 조문 |
|---|------|--------------|---------|
| 1 | "소득세법 제47조의 현행 근로소득공제 내용을 알려주세요." | `search_korean_law(law_name="소득세법", article_no="47")` | 소득세법 제47조 |
| 2 | "민법 제1000조는 상속 순위를 어떻게 정하고 있나요?" | `(law_name="민법", article_no="1000")` | 민법 제1000조 |
| 3 | "근로기준법 제60조에 따라 3년 근속자의 연차유급휴가는 몇 일인가요?" | `(law_name="근로기준법", article_no="60")` | 근로기준법 제60조 |
| 4 | "부가가치세법 제26조 제1항에서 면세 대상 재화·용역은 무엇인가요?" | `(law_name="부가가치세법", article_no="26")` | 부가가치세법 제26조 |

**1, 2번이 발표에서 가장 깔끔** — 조문이 짧고 누구나 결과 이해 가능.
**3, 4번은 tax/labor 특화** — 우리 fine-tune 어댑터 연계 가능 (단, tool-use는 base 모델로 시연하는 게 깨끗함).

---

## 5. 녹화 체크리스트

- [ ] vllm_tool 세션 살아있음 (`curl /v1/models`)
- [ ] MCP 엔드포인트 응답 (2.2 ping)
- [ ] Streamlit 포트 8700 포워딩 성공
- [ ] 첫 질문 warm-up (compile + tool-call 파서 초기화, 5~15초 지연)
- [ ] 질문당 max_tokens 2048 이상
- [ ] 녹화 대기 시간(1차 응답 2~5초, MCP 2~3초, 2차 응답 5~10초)에 유의
- [ ] 백업 녹화: 동일 질문 2회 녹화

---

## 6. 장애 시 폴백

| 증상 | 원인 | 대응 |
|------|------|------|
| tool_call이 안 나옴 | `--tool-call-parser` 옵션 누락 | vLLM 재기동 시 옵션 포함 확인 |
| `qwen3_coder` 파서 미지원 경고 | vLLM 버전 | 최신 vLLM 0.17+ 인지 확인 (`vllm --version`) |
| MCP 404/타임아웃 | 엔드포인트 장애 | `LAW_OC` 유효성 / `fly.dev` 헬스체크. 임시로 `search_korean_law` tool을 제거하고 bare chat으로 폴백 |
| 2차 호출 후 답변 빔 | tool_message 길이 초과 | `result[:3000]` 으로 잘라 재호출 (이미 반영됨) |
| tool_call arguments에 "제 / 조" 포함 | Nemotron이 가끔 포함 | mcp_call 내부에서 정규식으로 숫자만 추출 (현재는 그대로 전달, 실패 시 강화) |

---

## 7. 발표 내레이션 템플릿

> "이건 라이브입니다. 사전 녹화 아닙니다. 제가 지금 '소득세법 제47조의 근로소득공제를 알려주세요' 라고 입력합니다.
>
> **단계 1**: Nemotron 3 Nano 30B A3B가 이 질문을 받자마자 자체 지식으로 답하지 않고, 우리가 등록한 `search_korean_law` 도구를 호출하기로 결정했습니다. 인자는 `{law_name: '소득세법', article_no: '47'}`. 이 결정 자체가 Nemotron의 function-calling 능력입니다.
>
> **단계 2**: 우리 코드가 이 tool_call을 받아 Korean Law MCP에 전달합니다. MCP는 법제처 공식 Open API를 17개 도구로 감싼 오픈소스입니다. 지금 이 순간 실제 법제처 서버로 HTTPS 요청이 갑니다. 이 조문 원문이 화면에 뜨는 것이 그 증거입니다.
>
> **단계 3**: Nemotron이 조문 원문을 보고 최종 답을 생성합니다. 기억이 아니라 방금 읽은 텍스트를 근거로 답하니 환각이 원천 차단됩니다.
>
> 이것이 저희가 왜 Nemotron + MCP 조합에 집중했는지의 실증입니다."

---

## 8. 관련 파일
- `demo/nemotron_tool_call.py` — CLI 구현 (2026-04-21 작성, 검증된 2-turn 구조)
- `demo/app_toolcall.py` — Streamlit UI (2026-04-22 본 세션 추가)
- `scripts/launch_vllm.sh` — FP8 기반 과거 기동 스크립트 (본 데모는 BF16 기반, §2.1 참조)
- `pipeline/validators/citation_validator.py` — L2 MCP `verify_citations` (파이프라인 내 동일 MCP 재사용 증거)

## 9. 레퍼런스
- [Korean Law MCP (fly.dev)](https://korean-law-mcp.fly.dev)
- [법제처 Open API](https://open.law.go.kr)
- [vLLM tool-calling 문서](https://docs.vllm.ai/en/latest/features/tool_calling.html)
