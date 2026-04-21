# 7. WSL 환경 세팅 (Brev 대응)

> **왜 WSL인가?** Brev CLI와 일부 NVIDIA 개발 도구가 Windows 네이티브에서 제대로 동작하지 않음. WSL2로 옮기면 리눅스 네이티브 환경으로 통일되어 Brev/vLLM/NeMo 생태계와 완벽히 호환됨.

## 7.1 WSL2 설치 (Windows 11)

### 이미 WSL 사용 중인지 확인

```powershell
# PowerShell (관리자 권한)
wsl -l -v
```

출력 예시:
```
NAME            STATE           VERSION
Ubuntu-22.04    Running         2
```

위가 보이면 이미 설치됨 → [7.2](#72-ubuntu-초기-세팅)로 이동.

### 미설치 시 설치

```powershell
# PowerShell (관리자 권한)
wsl --install -d Ubuntu-22.04
```

설치 후 재부팅 → 사용자명/비밀번호 설정.

### Ubuntu 버전 확인
- **Ubuntu 22.04 LTS 권장** (NVIDIA 공식 CUDA 지원)
- 24.04도 가능하지만 CUDA 호환 문제 가끔 있음

## 7.2 Ubuntu 초기 세팅

### 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 필수 패키지 설치

```bash
sudo apt install -y \
  build-essential \
  git \
  curl \
  wget \
  tmux \
  htop \
  jq \
  unzip \
  ca-certificates \
  software-properties-common
```

### Python 3.10+ 확인

```bash
python3 --version
# Python 3.10.x 이상이어야 함

# 없다면:
sudo apt install -y python3.10 python3.10-venv python3-pip
```

### Node.js 20+ 설치 (Korean Law MCP용)

```bash
# NodeSource 공식 설치
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

node --version  # v20.x.x
npm --version
```

## 7.3 Brev CLI 설치 (WSL)

```bash
# Brev CLI 공식 설치 스크립트
curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/bin/install-latest.sh | sh

# PATH 추가
echo 'export PATH="$HOME/.brev/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

brev --version
```

### Brev 로그인 + 인스턴스 연결

```bash
brev login
# 브라우저 열림 → 인증

brev ls
# 생성한 인스턴스 목록 확인

# 인스턴스에 SSH 접속
brev shell <인스턴스명>

# 또는 VSCode로 접속
brev open <인스턴스명>
```

## 7.4 WSL에서 프로젝트 이동

### 옵션 A: 기존 Windows 경로를 WSL에서 접근 (느림)
```bash
cd /mnt/c/Users/ejeong015/Project/nvidia-hackathon
# 작동은 하지만 파일 I/O 느림 (Windows ↔ Linux 파일시스템 경계)
```

### 옵션 B: WSL 네이티브 경로로 clone (권장)
```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/uihyeon1229/jerry-is-good.git nvidia-hackathon
cd nvidia-hackathon
```

→ **옵션 B 사용. 속도·호환성 모두 좋음.**

### Git 사용자 정보 (최초 1회)
```bash
git config --global user.name "ejeong015"
git config --global user.email "본인이메일"
```

## 7.5 NVIDIA 드라이버 (WSL2)

### 사전 확인
Windows 호스트에 **NVIDIA 드라이버가 설치**되어 있어야 WSL2에서 GPU 접근 가능.

```bash
# WSL 내부에서
nvidia-smi
```

성공 시 GPU 정보 출력. 실패 시:

1. **Windows**에 최신 NVIDIA 드라이버 설치
   - https://www.nvidia.com/Download/index.aspx
   - **WSL2-ready 드라이버** (대부분 최신 버전이면 OK)
2. WSL 재시작: `wsl --shutdown` (PowerShell) → 다시 진입

### CUDA Toolkit (WSL용)

```bash
# CUDA 12.8 기준 (Nemotron Nano 가이드 호환)
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin
sudo mv cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600

wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda-repo-wsl-ubuntu-12-8-local_12.8.0-1_amd64.deb
sudo dpkg -i cuda-repo-wsl-ubuntu-12-8-local_12.8.0-1_amd64.deb
sudo cp /var/cuda-repo-wsl-ubuntu-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt update
sudo apt install -y cuda-toolkit-12-8

# PATH
echo 'export PATH=/usr/local/cuda-12.8/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

nvcc --version
```

> **주의**: Brev 인스턴스에는 이미 CUDA가 설치되어 있음. 위는 **로컬 WSL 개발용**. Brev에서 실제 학습·서빙은 인스턴스 내부에서 진행.

## 7.6 Python venv (WSL 로컬 — 경량 개발용)

Brev 인스턴스에 올리기 전 **로컬에서 스크립트 검증**할 때 사용.

```bash
cd ~/projects/nvidia-hackathon
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install \
  openai \
  pandas \
  pyarrow \
  requests \
  pydantic \
  jinja2 \
  python-dotenv
```

> Nemotron/vLLM은 로컬 WSL에선 안 돌린다 (GPU 메모리 부족). 대신 Brev Nemotron API를 호출하는 **클라이언트 코드**만 로컬에서 개발/테스트.

## 7.7 Korean Law MCP (WSL 로컬 테스트)

```bash
# OC 키 설정 (bash)
export LAW_OC="발급받은키"

# 영구 저장
echo 'export LAW_OC="발급받은키"' >> ~/.bashrc

# 테스트
npx korean-law-mcp "소득세법 제20조"
```

### .env 파일로 관리 (권장)

```bash
cat > ~/projects/nvidia-hackathon/.env <<EOF
LAW_OC=발급받은키
HF_TOKEN=허깅페이스토큰
BREV_INSTANCE_URL=http://인스턴스IP:5000/v1
EOF

# .gitignore에 이미 .env 있음 (노출 방지)
```

파이썬에서 로드:
```python
from dotenv import load_dotenv
import os

load_dotenv()
law_oc = os.environ["LAW_OC"]
```

## 7.8 Windows ↔ WSL 파일 공유 팁

### WSL → Windows 탐색
```bash
# WSL 파일 → Windows 탐색기로 열기
explorer.exe .
```

### Windows → WSL 접근
```powershell
# PowerShell에서
cd \\wsl.localhost\Ubuntu-22.04\home\<사용자명>\projects\nvidia-hackathon
```

### VSCode로 WSL 프로젝트 열기 (추천)
```bash
# WSL 내부에서
cd ~/projects/nvidia-hackathon
code .
```
- VSCode가 "Remote - WSL" 확장 자동 설치 제안 → 수락
- 이후 VSCode가 WSL 내부에서 실행되어 경로/환경 모두 리눅스 네이티브

## 7.9 Brev 인스턴스 ↔ 로컬 WSL 동기화

### 코드 동기화 (git push/pull)
```bash
# 로컬 WSL에서 개발 → push
git add . && git commit -m "..." && git push

# Brev 인스턴스에서 pull
brev shell <인스턴스명>
cd ~/projects/nvidia-hackathon
git pull
```

### 결과물 다운로드 (Brev → 로컬)
```bash
# 로컬 WSL에서
brev cp <인스턴스명>:~/workspace/output/train.jsonl ./output/
```

### 대용량 모델 체크포인트
- Brev 인스턴스 내부에 저장 (로컬 내려받지 말 것)
- 필요시 HuggingFace Hub에 업로드 후 다시 다운로드

## 7.10 tmux 세션 (밤샘 학습 필수)

```bash
# 세션 시작
tmux new -s sft-training

# 학습 스크립트 실행
python training/sft_qwen_1.5b.py

# 세션 detach: Ctrl+b → d

# 다시 접속
tmux attach -t sft-training

# 세션 목록
tmux ls
```

→ SSH 끊어져도 학습 계속 진행.

## 7.11 트러블슈팅

### `nvidia-smi` not found in WSL
- Windows 호스트에 최신 NVIDIA 드라이버 설치 확인
- `wsl --shutdown` 후 재진입

### WSL이 느림 (디스크 I/O)
- `/mnt/c/` 경로 대신 `~/` (WSL 네이티브 파일시스템) 사용
- `.wslconfig` 메모리 할당 조정:
  ```ini
  # C:\Users\<사용자>\.wslconfig
  [wsl2]
  memory=16GB
  processors=8
  swap=8GB
  ```

### Brev CLI 명령 안 됨
- PATH 재설정: `source ~/.bashrc`
- 재설치: `curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/bin/install-latest.sh | sh`

### Git push 인증 실패
- GitHub Personal Access Token 발급
  - https://github.com/settings/tokens
  - `repo` 스코프 선택
- `git push` 시 username = GitHub ID, password = PAT

### `npx korean-law-mcp` 실패
- Node.js 버전 확인 (`node -v` → v18 이상)
- OC 키 환경변수 확인 (`echo $LAW_OC`)

## 7.12 WSL 세팅 체크리스트

각 팀원 WSL 환경에서 체크:

- [ ] WSL2 Ubuntu 22.04 설치
- [ ] `nvidia-smi` GPU 정보 출력 확인
- [ ] Python 3.10+, Node.js 20+ 설치
- [ ] Brev CLI 설치 + 로그인
- [ ] Git 사용자 정보 설정
- [ ] `git clone` 으로 프로젝트 clone
- [ ] `.env` 파일 생성 + OC 키 저장
- [ ] `npx korean-law-mcp "소득세법 제20조"` 성공
- [ ] VSCode Remote WSL 동작
- [ ] tmux 사용법 숙지

---

## 🚨 핵심 요약 (급할 때)

```bash
# 1. WSL 진입
wsl

# 2. 프로젝트 clone
cd ~/projects
git clone https://github.com/uihyeon1229/jerry-is-good.git nvidia-hackathon
cd nvidia-hackathon

# 3. Brev 로그인
brev login
brev ls

# 4. Brev 인스턴스 접속
brev shell <인스턴스명>

# 5. 인스턴스에서 작업
```
