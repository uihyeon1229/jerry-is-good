# Windows PowerShell Claude Code — Tool-use 데모 녹화 가이드

> **사용법**: PowerShell(관리자 불필요)에서 Claude Code 실행 후 **이 문서를 그대로 전달**하세요.
> Claude Code는 아래 단계를 순차 실행해 `C:\Users\<USER>\Videos\toolcall_demo.mp4` 를 생성합니다.

---

## 0. 전제 조건 (WSL 쪽, 사용자가 미리 해둘 것)

이 두 개는 WSL 터미널에서 **먼저 실행되어 유지되고 있어야** 합니다.

```bash
# WSL 터미널 1 — Brev 포트포워딩 (vLLM + Streamlit)
brev port-forward jerryisgood-h100-80gib-vram-sxm5 -p 5000:5000 -p 8700:8700

# WSL 터미널 2 — Brev 인스턴스 내 tmux 세션 확인 (vllm_tool 살아있어야 함)
brev exec jerryisgood-h100-80gib-vram-sxm5 "tmux ls && curl -s http://localhost:5000/v1/models | head -c 200"
# 기대 출력: vllm_tool 세션 + {"id":"nemotron",...}

# (옵션) Streamlit UI 도 Brev 인스턴스에서 띄우기
brev exec jerryisgood-h100-80gib-vram-sxm5 "cd /home/shadeform/jerry-is-good && source /home/shadeform/track3/bin/activate && pip install -q streamlit && tmux new -d -s st_tool 'LAW_OC=didwjs12 VLLM_BASE_URL=http://localhost:5000/v1 VLLM_MODEL=nemotron streamlit run demo/app_toolcall.py --server.port 8700 --server.address 0.0.0.0'"
```

`http://localhost:8700` 이 Windows 브라우저에서 열리면 전제 조건 완료.

---

## 1. Claude Code가 PowerShell에서 실행할 작업 (순서대로)

### 1.1 ffmpeg 설치 확인 / 설치

```powershell
# 먼저 설치 여부 확인
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ff) {
    Write-Host "ffmpeg 미설치 — winget으로 설치"
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    # 설치 직후 PATH 갱신
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
ffmpeg -version | Select-String "^ffmpeg version"
```

### 1.2 브라우저 열기 (Streamlit UI)

```powershell
Start-Process "chrome.exe" "http://localhost:8700"
# Chrome 이 없으면 기본 브라우저:
# Start-Process "http://localhost:8700"
Start-Sleep -Seconds 5   # 페이지 로드 대기
```

### 1.3 녹화 시작 (백그라운드)

```powershell
$OutDir = "$env:USERPROFILE\Videos"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$OutFile = Join-Path $OutDir ("toolcall_demo_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".mp4")

$ffArgs = @(
    "-y",
    "-f", "gdigrab",
    "-framerate", "30",
    "-i", "desktop",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-pix_fmt", "yuv420p",
    "-crf", "23",
    $OutFile
)

$proc = Start-Process -FilePath "ffmpeg" -ArgumentList $ffArgs -NoNewWindow -PassThru
Write-Host "녹화 시작: $OutFile  (PID=$($proc.Id))"
Write-Host ""
Write-Host "──────────────────────────────────────────────"
Write-Host "이제 브라우저에서 시연을 진행하세요:"
Write-Host "  1) http://localhost:8700 에 접속"
Write-Host "  2) '빠른 샘플' 드롭다운에서 '소득세법 제47조...' 선택"
Write-Host "  3) '▶ Nemotron에게 질문' 클릭"
Write-Host "  4) 3단계(1차/MCP/2차) 렌더링 전부 완료 대기"
Write-Host "  5) 원하면 질문 2~3개 반복"
Write-Host "──────────────────────────────────────────────"
Read-Host "시연이 끝나면 Enter를 눌러 녹화 종료"
```

### 1.4 녹화 종료

```powershell
# ffmpeg 은 stdin 으로 'q' 를 받으면 정상 종료 — 하지만 background 기동이라 바로 Stop-Process
Stop-Process -Id $proc.Id -Force
Start-Sleep -Seconds 1
Write-Host "녹화 저장 완료: $OutFile"
Write-Host "파일 크기: $([math]::Round((Get-Item $OutFile).Length / 1MB, 1)) MB"
Write-Host "재생: explorer.exe $OutFile"
```

### 1.5 (선택) 파일 열기 / 재생 확인

```powershell
# 녹화본 확인
explorer.exe (Split-Path $OutFile)
# 또는 바로 Movies & TV 앱으로 재생
Start-Process $OutFile
```

---

## 2. 결과물 공유 방법

파일 용량에 따라:

| 용량 | 권장 공유 경로 |
|------|-------------|
| < 5 MB | 레포에 바로 commit (`demo/recordings/`) |
| 5~100 MB | Git LFS 또는 WeTransfer 링크를 문서 19번에 추가 |
| > 100 MB | YouTube **unlisted** 업로드 → 링크만 문서 19번에 삽입 |

---

## 3. 장애 시 폴백

| 증상 | 원인 | 대응 |
|------|------|------|
| `winget: 명령을 찾을 수 없습니다` | Windows 10 older | [ffmpeg.org](https://ffmpeg.org/download.html) 에서 직접 다운로드, zip 풀어서 `bin\ffmpeg.exe` 경로를 `$env:Path` 에 추가 |
| `'ffmpeg'은(는) 내부 또는 외부 명령 아님` | 설치 직후 PATH 미반영 | PowerShell 새로 열거나 1.1 의 PATH 갱신 라인 재실행 |
| `http://localhost:8700` 접속 안 됨 | Brev 포트포워딩 끊김 | WSL 에서 `brev port-forward ... -p 8700:8700` 재실행 |
| 녹화된 mp4 가 0 바이트 | 기본 화면에 커서 없는 상태로 gdigrab 실패 | `-framerate 15` 로 낮춰 재시도 / DirectX 버전 확인 |
| 녹화 화면에 다른 창 섞임 | gdigrab 은 전체 데스크톱 | Win+Tab 으로 Chrome 만 있는 가상 데스크톱으로 이동 후 녹화 |

---

## 4. 한 번에 실행하는 원라이너 (요약)

익숙해진 뒤 전체 과정을 한 줄로:

```powershell
winget install --id Gyan.FFmpeg -e --silent; Start-Process "chrome.exe" "http://localhost:8700"; Start-Sleep 5; $f="$env:USERPROFILE\Videos\toolcall_demo.mp4"; $p=Start-Process ffmpeg -ArgumentList "-y -f gdigrab -framerate 30 -i desktop -c:v libx264 -preset ultrafast -pix_fmt yuv420p `"$f`"" -PassThru -NoNewWindow; Read-Host "시연 끝나면 Enter"; Stop-Process $p.Id -Force; Write-Host "저장: $f"
```

---

## 5. Claude Code 에게 전달할 프롬프트 예시

PowerShell 에서 `claude` 실행 후 다음 메시지:

> 프로젝트 `C:\Users\ejeong015\Project\nvidia-hackathon` 안의 `demo/record_windows_guide.md` 를 순서대로 따라 진행해줘.
> WSL 쪽 §0 전제 조건은 내가 이미 해뒀고, 브라우저에서 `http://localhost:8700` 접속이 가능한 상태야.
> §1.1 ~ §1.4 까지 실행하고, 시연 중간(§1.3 의 `Read-Host`)에는 내가 Enter를 누를 때까지 기다려.
> 완료되면 저장된 mp4 경로만 마지막에 출력해.
