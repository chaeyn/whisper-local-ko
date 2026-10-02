# Whisper Local KO

[English](README.md) · [사용 설명서](docs/user-guide.ko.md) · [기여 안내](CONTRIBUTING.ko.md) · [시험 기록](VALIDATION.md)

한국어 또는 영어 음성을 내 컴퓨터에서 한국어 텍스트로 변환합니다.
로컬 오디오 파일을 선택하거나 마이크로 실시간 자막을 만들 수 있습니다.

- 터미널 화면(TUI), 명령줄(CLI), 데스크톱 창(GUI)을 제공합니다.
- TUI 파일 탐색기에서 오디오를 선택합니다.
- 파일 변환 중 진행률을 표시합니다.
- 원본 옆이나 지정한 경로에 UTF-8 텍스트를 저장합니다.
- 오디오와 결과를 내 컴퓨터에서 처리합니다. 계정이나 API 키가 필요하지 않습니다.

화면은 영어로 표시합니다. 결과는 한국어로 저장합니다.
Whisper가 음성을 받아씁니다. 로컬 번역 모델이 영어 텍스트를 한국어로 번역합니다.
결과를 사용하기 전에 내용을 확인하세요.

## 지원 환경

| 환경 | 아키텍처 | Python | 실시간 오디오 입력 |
| --- | --- | --- | --- |
| macOS | Apple Silicon / ARM64 | 3.11, 3.12 | FFmpeg AVFoundation |
| Linux 데스크톱 | x86_64 | 3.11, 3.12 | FFmpeg PulseAudio; PulseAudio 호환 기능을 켠 PipeWire |
| Windows | x86_64 | 3.11, 3.12 | FFmpeg DirectShow |

이 버전은 CPU로 처리합니다. Intel Mac, ARM Linux, ARM Windows는 지원 대상에 포함하지 않습니다.
현재 고정한 PyTorch 버전에는 Intel macOS용 wheel이 없습니다.

TUI에는 60열 × 24행 이상의 대화형 터미널이 필요합니다.
GUI에는 Tk와 데스크톱 세션이 필요합니다. CLI는 화면 없이 실행할 수 있습니다.
Linux 마이크 입력에는 실행 중인 PulseAudio 호환 서버가 필요합니다.

자동 시험과 실제 장치 시험은 확인 범위가 다릅니다.
통과한 시험과 미검증 항목은 [VALIDATION.md](VALIDATION.md)를 확인하세요.
이 버전의 실제 마이크 캡처는 검증하지 않았습니다.

## 설치

먼저 Python 3.11 또는 3.12와 FFmpeg를 설치하세요.
macOS와 Linux에서는 GitHub 릴리스 설치 스크립트를 사용하세요. Git은 필요하지 않습니다.
첫 모델 다운로드에는 인터넷 연결과 디스크 여유 공간이 필요합니다.

### macOS

[Homebrew](https://brew.sh/)가 없으면 먼저 설치하세요.
다음 명령을 실행하세요.

```sh
brew install python@3.11 python-tk@3.11 ffmpeg
curl -fsSL https://github.com/chaeyn/whisper-local-ko/releases/latest/download/install.sh | sh -s -- --run
```

### Linux

Ubuntu 24.04에서 다음 명령을 실행하세요.

```sh
sudo apt update
sudo apt install curl python3 python3-venv python3-tk ffmpeg pulseaudio-utils
curl -fsSL https://github.com/chaeyn/whisper-local-ko/releases/latest/download/install.sh | sh -s -- --run
```

다른 배포판에서는 같은 기능의 패키지를 설치하세요.
`python3 --version`이 3.11 또는 3.12인지 확인하세요.
설치 스크립트는 시스템 패키지를 설치하지 않습니다.

설치 스크립트는 GitHub Releases에서 버전을 고정한 소스 압축 파일을 받습니다.
설치 전에 릴리스의 SHA-256 체크섬과 압축 파일을 대조합니다.
설치 경로는 `~/.local/share/whisper-local-ko`이고 실행 파일은 `~/.local/bin/whisper-ko`입니다.
`--run`을 붙이면 설치 후 TUI를 엽니다. 설치만 하려면 `--run`을 빼세요.
나중에 앱을 실행하려면 다음 명령을 사용하세요.

```sh
"$HOME/.local/bin/whisper-ko"
```

새 설치가 실패하면 설치 스크립트는 이전 설치를 유지합니다.
셸 설정 파일은 바꾸지 않습니다.
설치 경로 지정, 업데이트, 삭제는 [사용 설명서](docs/user-guide.ko.md#릴리스-설치-옵션)를 확인하세요.

### Windows

PowerShell에서 필수 프로그램을 설치하세요.

```powershell
winget install --exact --id Python.Python.3.11
winget install --exact --id Gyan.FFmpeg
```

새 PowerShell 창을 여세요. 릴리스 패키지를 설치하세요.

```powershell
$WhisperVenv = Join-Path $env:LOCALAPPDATA "whisper-local-ko\.venv"
py -3.11 -m venv "$WhisperVenv"
& "$WhisperVenv\Scripts\python.exe" -m pip install --upgrade pip
& "$WhisperVenv\Scripts\python.exe" -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
& "$WhisperVenv\Scripts\python.exe" -m pip install https://github.com/chaeyn/whisper-local-ko/releases/download/v0.1.2/whisper_local_ko-0.1.2-py3-none-any.whl
& "$WhisperVenv\Scripts\whisper-ko.exe" doctor --no-gui --tui
& "$WhisperVenv\Scripts\whisper-ko.exe"
```

Python 3.12를 쓰려면 `-3.11`을 `-3.12`로 바꾸세요.
이 명령은 릴리스 wheel을 사용합니다. Git 설치와 가상환경 활성화는 필요하지 않습니다.
새 PowerShell 창에서 앱을 실행하려면 다음 명령을 사용하세요.

```powershell
& "$env:LOCALAPPDATA\whisper-local-ko\.venv\Scripts\whisper-ko.exe"
```

### 기존 Python 환경

Python 3.11 또는 3.12 가상환경을 사용하세요.
Linux와 Windows에서는 CPU용 PyTorch를 먼저 설치하세요.

```sh
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
```

그다음 GitHub Releases의 wheel을 설치하세요.

```sh
python -m pip install https://github.com/chaeyn/whisper-local-ko/releases/download/v0.1.2/whisper_local_ko-0.1.2-py3-none-any.whl
whisper-ko doctor --no-gui --tui
whisper-ko
```

패키지 이름은 `whisper-local-ko`입니다. 실행 명령은 `whisper-ko`입니다.
이 방법은 지원하는 각 OS에서 사용할 수 있으며 PyPI 배포가 필요하지 않습니다.
소스 설치와 개발 절차는 [CONTRIBUTING.ko.md](CONTRIBUTING.ko.md#개발-환경-준비)를 확인하세요.

## 파일 변환

macOS와 Linux에서는 `"$HOME/.local/bin/whisper-ko"`를 실행하세요.
Windows에서는 위의 설치된 실행 파일을 사용하세요.

1. `b`를 눌러 파일 탐색기를 여세요.
2. 오디오 파일을 선택하세요.
3. `l`을 눌러 음성 언어를 선택하세요.
4. `m`을 눌러 모델을 선택하세요. 첫 시험에는 `tiny`를 사용하세요.
5. `s`를 눌러 변환을 시작하세요.
6. 한국어 결과와 저장 경로를 확인하세요.

파일 변환의 기본 모델은 `small`입니다. 기본 언어 설정은 자동 감지입니다.
짧은 녹음에서는 `Korean` 또는 `English`를 선택하면 언어 감지 오류를 줄일 수 있습니다.

앱은 `meeting.m4a` 옆에 `meeting.ko.txt`를 저장합니다.
다른 경로에 저장하려면 `o`를 누르세요. 결과 폴더는 먼저 만드세요.
기존 결과가 있으면 TUI에서 교체 여부를 묻습니다.

| 키 | 동작 |
| --- | --- |
| `b` | 로컬 파일 탐색 |
| `f` / `o` | 입력 경로 / 출력 경로 편집 |
| `l` / `m` | 다음 언어 / 모델 선택 |
| `s` | 파일 변환 시작 |
| `v` / `d` | 마이크 자막 시작 / 마이크 선택 |
| `r` | 선택한 파일을 원래 시간 흐름에 맞춰 처리 |
| `x` | 실시간 입력 중지 후 버퍼의 오디오 처리 |
| `↑` / `↓` / `PgUp` / `PgDn` | 결과 스크롤 |
| `q` | 종료. 작업 중이면 확인 표시 |

경로 편집, 파일 선택, 진행률, 중지 동작은 [사용 설명서](docs/user-guide.ko.md)에서 설명합니다.

## CLI와 GUI

다음 예시는 `PATH`에서 찾을 수 있는 `whisper-ko`를 사용합니다.
위의 실행 파일 전체 경로에도 같은 인수를 전달할 수 있습니다.
현재 터미널의 `PATH` 설정은 [명령과 실행 환경](docs/user-guide.ko.md#명령과-실행-환경)을 확인하세요.

```bash
whisper-ko transcribe "meeting.m4a" --language ko --model small
whisper-ko transcribe "interview.mp3" --language en --output "interview.ko.txt"
whisper-ko gui
whisper-ko doctor
```

CLI는 출력 파일이 있으면 중단합니다.
기존 파일을 교체할 때만 `--overwrite`를 추가하세요.
GUI는 결과를 교체하기 전에 확인을 요청합니다.
결과는 APFS, ext4, NTFS 등 하드 링크를 지원하는 로컬 파일 시스템에 저장하세요.
exFAT, FAT 또는 지원하지 않는 네트워크 드라이브에서는 홈 폴더의 출력 경로를 선택하세요.

## 실시간 자막

```bash
whisper-ko live --list-devices
whisper-ko live --language ko --model tiny
```

실시간 CLI는 기본으로 `tiny`, 한국어 음성, 6초 오디오 묶음을 사용합니다.
TUI는 화면에서 선택한 언어와 모델을 사용합니다.
`Korean`과 `tiny`를 선택한 뒤 `v`를 누르세요.

`--device`에는 `--list-devices`에서 확인한 장치 ID를 넣으세요.
Windows의 `default`는 DirectShow 목록의 첫 번째 마이크를 선택합니다.
Windows 시스템 기본 장치 설정과 다를 수 있습니다.

실시간 CLI에서 `Ctrl+C`를 눌러 입력을 중지하세요.
앱은 버퍼에 남은 오디오를 처리하고 완성한 자막을 저장합니다.
실시간 모드는 새 출력 파일이 필요합니다. 시작할 때 기존 결과를 교체하지 않습니다.

첫 자막은 모델 로딩 후 오디오 한 묶음의 길이와 인식 시간이 지나야 표시됩니다.
묶음 경계에서 단어를 놓칠 수 있습니다. 작은 목소리는 건너뛸 수 있습니다.
단어별 즉시 갱신과 화자 구분은 제공하지 않습니다.

## 데이터, 모델, 도움말

앱은 오디오와 결과 텍스트를 외부 서비스로 보내지 않습니다.
패키지 설치와 모델 다운로드는 외부 서버에 접속합니다.
다운로드한 모델은 사용자 캐시에 남습니다.
캐시를 지우거나 진단 결과를 공유하기 전에 [데이터와 모델 설명](docs/user-guide.ko.md#데이터와-모델)을 확인하세요.

- 설치와 장치 오류는 [문제 해결](docs/user-guide.ko.md#문제-해결)을 확인하세요.
- 재현할 수 있는 문제는 [버그 보고](https://github.com/chaeyn/whisper-local-ko/issues/new/choose)에 등록하세요.
- 코드, 시험, 번역 기여는 [CONTRIBUTING.ko.md](CONTRIBUTING.ko.md)를 확인하세요.
- 비공개 보안 신고는 [SECURITY.md](SECURITY.md)를 확인하세요.

## 라이선스와 참고 프로젝트

프로젝트 코드는 [MIT License](LICENSE)를 사용합니다.
Whisper와 번역 모델에는 각각의 라이선스가 적용됩니다.
[모델 출처](docs/user-guide.ko.md#모델-출처)와 [외부 구성요소 안내](THIRD_PARTY_NOTICES.md)를 확인하세요.

[Buzz와 Lazygit](docs/project-references.md)의 문서 구조와 기여 안내를 참고했습니다.
영문과 한국어 문서에는 [ASD-STE100에서 참고한 작성 원칙](docs/writing-guide.md)을 적용합니다.
이 프로젝트는 공식 STE 준수나 인증을 주장하지 않습니다.
