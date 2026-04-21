# 5. 대회 전 준비 체크리스트

> **지금 당장 해둬야 Day1이 편해집니다.** 팀원 각자 해당 항목을 체크하세요.

## 5.1 전원 (필수)

- [ ] 이 리포지토리 clone 완료
- [ ] 슬랙/디스코드 등 팀 커뮤니케이션 채널 참여
- [ ] 대회 일정·장소 확인 (입장 시간, 발표 순서)

## 5.2 역할별 체크리스트

### 🧑‍💻 A. 인프라/서빙 담당

- [ ] **Brev.dev 가입** — https://brev.dev
- [ ] 스폰서 크레딧 $1000 연동 확인
- [ ] H100 인스턴스 생성 UI 숙지 (실제 생성은 Day1에)
- [ ] SSH 공개키 Brev에 등록
- [ ] **HuggingFace 계정 + Read 토큰 발급** — https://huggingface.co/settings/tokens
- [ ] 로컬에 `ssh` 클라이언트 준비 (Windows면 WSL 또는 Windows Terminal)
- [ ] [vLLM 문서](https://docs.vllm.ai) 훑어보기 (30분)
- [ ] [Nemotron 3 Nano FP8 카드](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8) 확인

### 🧑‍🔬 B. 파이프라인 담당

- [ ] 로컬에 Python 3.10+ 설치 확인 (`python --version`)
- [ ] [NeMo Data Designer 문서](https://nvidia-nemo.github.io/DataDesigner/latest/) 훑어보기 (1시간)
- [ ] 가이드 노트북 로컬에서 코드만 열어보기 (실행은 Day1)
- [ ] [NeMo Curator GitHub](https://github.com/NVIDIA/NeMo-Curator) README 훑기
- [ ] [NeMo Guardrails 문서](https://github.com/NVIDIA/NeMo-Guardrails) README 훑기
- [ ] Pydantic v2 기본 문법 숙지 (이미 알면 skip)

### 📚 C. 도메인/시드 담당

- [ ] **법제처 OC 키 발급** (1분, 무료)
  - https://open.law.go.kr/LSO/openApi/guideList.do
  - 발급 후 팀에 공유 (슬랙/암호화된 채널)
- [ ] **Korean Law MCP 로컬 테스트**
  - Node.js 18+ 설치 확인 (`node --version`)
  - 아래 명령 성공 확인:
    ```bash
    # PowerShell
    $env:LAW_OC="발급받은키"
    npx korean-law-mcp "소득세법 제20조"

    # Mac/Linux
    export LAW_OC=발급받은키
    npx korean-law-mcp "소득세법 제20조"
    ```
- [ ] 4개 세목별 주요 조문 목록 각 10개씩 초안 작성
  - 소득세: §20, §24, §27, §51, §55 등
  - 상증세: §13, §18, §53, §60, §63 등
  - 법인세: §15, §23, §25, §28, §55 등
  - 부가세: §3, §29, §38, §39, §48 등
- [ ] CoT 예제 5개 수작업 작성 (Judge Few-shot용)
  - 세목별 1~2개씩
  - 형식: 조문 인용 → 사실관계 → 계산/해석 → 결론

### 🎤 D. 평가/발표 담당

- [ ] **발표 템플릿 준비**
  - NVIDIA 스폰서 로고, 해커톤 로고 확보
  - 회사/팀 로고 준비
  - 16:9 비율, 한국어 + 핵심 용어 영어 병기 권장
- [ ] **벤치마크 20문제 초안 작성** (C 담당이 리뷰)
  - 세목별 5문제 × 4세목
  - 난이도 분포: 기초 6 / 중급 10 / 고급 4
  - 각 문제에 예상 정답 + 근거 조문 명시
- [ ] 발표 흐름 초안 (슬라이드 제목만이라도)
  - [참고: 09-presentation-deck.md](./09-presentation-deck.md) ← 작성 예정
- [ ] 예상 Q&A 10개 준비 시작
  - "왜 Super가 아니고 Nano인가?", "왜 같은 Nemotron을 생성·학습에 모두 쓰는가?", "MCP 없이 가능한가?" 등

## 5.3 공용 자산 준비

- [ ] **Git 저장소** 생성 및 팀원 초대
- [ ] 이 `nvidia-hackathon/` 폴더 저장소에 push
- [ ] **공유 드라이브** (Google Drive 등) — 대용량 자료용
  - 발표자료, 데모 영상, 스크린샷
- [ ] **팀 암호 관리**
  - 법제처 OC 키
  - HuggingFace 토큰
  - Brev SSH 키
  - → 1Password / Bitwarden / 슬랙 DM 등

## 5.4 하드웨어/소프트웨어

### 개인 장비
- [ ] 노트북 충전기, 보조 배터리
- [ ] 유선 키보드/마우스 (편의)
- [ ] 듀얼 모니터 가능하면 준비
- [ ] 이어폰 (vLLM 학습 중 유튜브 튜토리얼용)

### 현장 대응
- [ ] 모바일 핫스팟 (현장 와이파이 불안정 대비)
- [ ] 식수, 간식
- [ ] 잠자리용 담요 / 안대 (밤샘 SFT 중 교대 수면)

## 5.5 미리 확인해둘 것

### 대회 운영
- [ ] 입장 시간, 발표 순서, 제출 방식
- [ ] 발표 시간 (10분? 15분?) — 슬라이드 수 결정
- [ ] 데모 허용 여부 (라이브 코드 vs 영상)
- [ ] 심사 기준 명시된 문서 확인
- [ ] 제출 형식 (GitHub repo? 발표자료 PDF?)

### 제공 자원 확정
- [ ] Brev 크레딧 실제 $1000 맞는지
- [ ] Friendli AI 크레딧 금액/사용법
- [ ] 스폰서 기술 지원 채널 (슬랙?) 있는지

## 5.6 긴급 대응 준비

### 백업 플랜
- [ ] **Friendli AI**에 Nemotron 엔드포인트 있는지 확인
  - vLLM 실패 시 즉시 전환 가능해야 함
- [ ] **NVIDIA Build API** 무료 tier 확인
  - 백업용 Nemotron 호출 가능
- [ ] **로컬 LLM** 준비 (Ollama로 소형 모델이라도)

### 컨택 포인트
- [ ] NVIDIA 멘토 연락처
- [ ] Brev 고객지원 채널
- [ ] 팀원 모두의 비상 연락처

---

## 🚨 가장 먼저 해야 할 3가지 (우선순위)

1. **법제처 OC 키 발급** — 5분, 모든 시드 수집의 전제
2. **Korean Law MCP 로컬 동작 확인** — 15분, 시드 스크립트 검증
3. **Brev 가입 + 크레딧 확인** — 10분, H100 접근성 확정

이 3가지만 되면 나머지는 대회 당일에 보완 가능.
