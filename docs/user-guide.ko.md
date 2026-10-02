# 사용 설명서

[English](user-guide.md) · [설치](../README.ko.md#설치)

## 명령과 실행 환경

OS에 맞는 [설치 절차](../README.ko.md#설치)를 따르세요.
릴리스 설치에는 저장소 소스가 필요하지 않습니다.

macOS와 Linux에서는 설치한 실행 파일을 사용하세요.

```sh
"$HOME/.local/bin/whisper-ko"
```

전체 경로 없이 `whisper-ko`를 사용하려면 현재 터미널의 `PATH`에 실행 파일 폴더를 추가하세요.

```sh
export PATH="$HOME/.local/bin:$PATH"
```

설치 스크립트는 셸 설정 파일을 바꾸지 않습니다.
이 명령은 현재 터미널과 여기서 시작한 프로세스에 적용됩니다.
`--bin-dir`로 경로를 지정했다면 해당 폴더를 사용하세요.

Windows PowerShell에서는 전체 경로로 실행하세요.

```powershell
& "$env:LOCALAPPDATA\whisper-local-ko\.venv\Scripts\whisper-ko.exe"
```

현재 PowerShell 창에서 `whisper-ko`를 사용하려면 다음과 같이 설정하세요.

```powershell
$env:Path = "$env:LOCALAPPDATA\whisper-local-ko\.venv\Scripts;$env:Path"
```

아래 예시는 `PATH`에서 `whisper-ko`를 찾을 수 있는 상태를 기준으로 합니다.
실행 파일 전체 경로에도 같은 인수를 전달할 수 있습니다.
상대 입력 경로와 출력 경로는 현재 폴더를 기준으로 해석합니다.

| 명령 | 용도 |
| --- | --- |
| `whisper-ko` 또는 `whisper-ko tui` | TUI 열기 |
| `whisper-ko gui` | 데스크톱 창 열기 |
| `whisper-ko transcribe FILE` | 로컬 파일 하나 변환 |
| `whisper-ko live` | 마이크 자막 시작 |
| `whisper-ko doctor` | 의존성, FFmpeg, Tk 창 검사 |
| `whisper-ko doctor --no-gui --tui` | 창을 열지 않고 의존성, FFmpeg, curses 검사 |
| `whisper-ko --help` | 명령 도움말 표시 |
| `whisper-ko live --help` | 실시간 모드 옵션 표시 |
| `whisper-ko --version` | 앱 버전 표시 |

`doctor`는 모델을 다운로드하거나 인식 품질을 측정하지 않습니다.
성공 시 종료 코드는 `0`입니다. 실행 오류는 `1`, 잘못된 명령 인수는 `2`입니다.

## 릴리스 설치 옵션

macOS와 Linux 설치 스크립트는 다음 옵션을 받습니다.

| 옵션 | 용도 |
| --- | --- |
| `--run` | 설치 후 TUI 열기 |
| `--prefix DIR` | 설치 데이터 폴더 지정. 기본값: `~/.local/share/whisper-local-ko` |
| `--bin-dir DIR` | 실행 파일 폴더 지정. 기본값: `~/.local/bin` |
| `--help` | 설치 도움말 표시 |

설치 경로를 지정하려면 다음 명령을 실행하세요.

```sh
curl -fsSL https://github.com/chaeyn/whisper-local-ko/releases/latest/download/install.sh | sh -s -- --prefix "$HOME/Apps/whisper-local-ko" --bin-dir "$HOME/bin" --run
```

`WHISPER_PYTHON` 환경 변수를 설정하면 설치 스크립트는 해당 Python을 사용합니다.
설정하지 않으면 설치된 Homebrew Python을 확인한 뒤 `PATH`의 Python 3.12, 3.11, `python3`를 확인합니다.
Python 3.11 또는 3.12와 FFmpeg가 필요합니다.

실행 전에 스크립트를 읽으려면 버전을 지정해 다운로드하세요.

```sh
curl -fL https://github.com/chaeyn/whisper-local-ko/releases/download/v0.1.2/install.sh -o install.sh
```

텍스트 편집기에서 `install.sh`를 읽으세요. 그다음 실행하세요.

```sh
sh install.sh --run
```

스크립트는 같은 릴리스에서 해당 버전의 소스 압축 파일과 `SHA256SUMS.txt`를 받습니다.
압축을 풀기 전에 소스 압축 파일의 체크섬을 확인합니다.
이 검사는 파일 불일치를 찾습니다. 다운로드한 설치 스크립트 자체의 진위는 확인하지 않습니다.

설치할 때마다 `<prefix>/releases/` 아래에 새 폴더를 만듭니다.
설치와 의존성 검사를 통과하면 실행 파일을 새 설치로 연결합니다.
해당 단계가 실패하면 기존 실행 파일과 설치를 유지합니다.
이전에 설치를 완료한 버전은 직접 지울 때까지 남습니다.

`--run`을 사용하면 설치 스크립트는 TUI 입력을 위해 `/dev/tty`를 엽니다.
이 옵션은 대화형 터미널에서 사용하세요.
터미널이 없으면 설치는 유지하지만 실행 단계는 실패합니다.
자동 작업에서는 설치만 한 뒤 터미널에서 실행 파일을 여세요.

## 소스 설치

개발하거나 저장소 소스를 사용하려면 [CONTRIBUTING.ko.md](../CONTRIBUTING.ko.md#개발-환경-준비)를 따르세요.
macOS와 Linux에서는 저장소 폴더에서 다음 명령을 실행하세요.

```sh
sh scripts/setup.sh --run
```

설치만 하려면 `--run`을 빼세요. 나중에 실행할 때는 `sh scripts/run.sh`를 사용하세요.
이 명령에는 스크립트 파일의 실행 권한이 필요하지 않습니다.
기존 `.venv`가 지원하는 Python 버전을 사용하면 해당 환경을 유지합니다.
오래된 환경 때문에 설치가 중단되면 `.venv` 폴더 이름을 바꾼 뒤 다시 설치하세요.

Windows에서는 소스의 설치 스크립트와 실행 스크립트를 사용하세요.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

위 명령은 해당 스크립트 프로세스의 실행 정책만 설정합니다.
Python 3.12를 쓰려면 설치 명령 끝에 `-PythonVersion 3.12`를 추가하세요.
실행 스크립트는 앱 인수를 받으며 현재 폴더를 유지합니다.

## 파일 선택과 경로 편집

TUI 탐색기는 폴더와 다음 확장자를 표시합니다.
`.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.aiff`, `.aac`, `.mp4`.
설치한 FFmpeg가 파일 내부의 코덱을 지원해야 합니다.
탐색기는 숨김 파일을 표시하지 않습니다.

1. `b`를 눌러 탐색기를 여세요.
2. 방향키로 항목을 선택하세요.
3. `Enter`를 눌러 폴더를 열거나 파일을 선택하세요.
4. `Backspace`를 눌러 상위 폴더로 이동하세요.
5. `Esc`를 눌러 탐색기를 닫으세요.

파일 선택은 로컬 경로를 엽니다. 외부로 업로드하지 않습니다.

입력 경로는 `f`, 출력 경로는 `o`로 편집하세요.
경로를 붙여 넣거나 기존 텍스트 끝에 입력하세요.
마지막 문자는 `Backspace`로 지우세요. 전체 입력은 `Ctrl+U`로 지우세요.
`Enter`나 `Esc`를 누르면 편집을 끝냅니다. 두 키 모두 입력한 값을 유지합니다.
경로 중간으로 입력 커서를 이동하는 기능은 제공하지 않습니다.

`Tab`과 `Shift+Tab`으로 항목을 이동하세요.
선택한 항목을 사용하려면 `Enter`를 누르세요.
CLI에서 공백이 있는 경로는 따옴표로 감싸세요.

## 언어와 모델 선택

| 모드 | 기본 언어 | 기본 모델 |
| --- | --- | --- |
| TUI 파일 변환과 실시간 자막 | 자동 감지 | `small` |
| 파일 CLI와 GUI | 자동 감지 | `small` |
| 실시간 CLI | 한국어 (`ko`) | `tiny` |

한국어 음성은 `ko`, 영어 음성은 `en`을 선택하세요.
자동 언어 감지가 필요하면 `auto`를 사용하세요.
앱은 한국어와 영어 입력을 지원합니다.
파일 변환 중 다른 언어를 감지하면 오류를 표시합니다.
실시간 모드는 지원하지 않는 언어의 묶음을 건너뛰고 상태를 표시합니다.

모델은 `tiny`, `base`, `small`, `medium`, `large` 중에서 선택합니다.
첫 실행에는 `tiny`로 전체 동작을 확인하세요.
큰 모델은 메모리, 디스크 공간, 처리 시간이 더 필요합니다.
기기별 속도와 메모리 사용량은 보장하지 않습니다.
이 버전은 GPU를 선택하지 않습니다.

## 결과와 진행률

파일 변환은 `<원본 이름>.ko.txt`를 UTF-8로 저장합니다.
경로를 바꾸려면 CLI의 `--output` 또는 TUI의 `o`를 사용하세요.
상위 폴더를 먼저 만드세요.
출력 경로는 원본 오디오 경로와 달라야 합니다.
APFS, ext4, NTFS 등 하드 링크를 지원하는 로컬 파일 시스템을 사용하세요.
exFAT, FAT 또는 지원하지 않는 네트워크 공유 폴더에서는 홈 폴더에 결과를 저장하세요.

CLI에서 기존 결과를 교체하려면 `--overwrite`가 필요합니다.
TUI와 GUI는 교체 전에 확인을 요청합니다.
파일 변환은 완성한 텍스트를 원자적 파일 연산으로 저장합니다.
저장 확정 전에 오류가 발생하면 기존 결과를 보존합니다.
강제 중지 후 출력 폴더에 `.whisper-*` 임시 파일이 남을 수 있습니다.
앱을 종료한 뒤 해당 임시 파일을 지우세요.

TUI는 단계별 진행률을 표시합니다.

| 단계 | 의미 |
| --- | --- |
| Loading | 모델 로딩 또는 다운로드. 측정한 백분율 없음 |
| Transcribing | 처리한 오디오 프레임의 비율 |
| Translating | 처리한 텍스트 묶음의 비율 |
| Saving | 완성한 결과 저장. 측정한 백분율 없음 |
| Done | 작업 완료 |

단계별 진행률은 전체 시간이나 남은 시간을 예측하지 않습니다.
파일 변환 중 `q` 또는 `Ctrl+C`를 누르면 중지 확인을 표시합니다.
`y`를 누르면 작업 프로세스를 종료하고 나갑니다. `n`을 누르면 계속합니다.
중지 직전에 변환을 완료했다면 결과 파일이 이미 저장됐을 수 있습니다.

GUI에서 파일, 언어, 모델을 선택하세요. 그다음 **Start transcription**를 선택하세요.
GUI는 결과를 화면에 표시하고 파일에 저장합니다.
결과 입력란을 편집해도 저장 파일은 바뀌지 않습니다.
GUI는 파일 변환을 제공합니다.

## 마이크 자막

사용할 수 있는 장치를 확인하세요.

```bash
whisper-ko live --list-devices
```

목록에 표시한 ID로 실행하세요.

```bash
whisper-ko live --device "DEVICE_ID" --language ko --model tiny --chunk-seconds 6 --output "session.ko.txt"
```

`DEVICE_ID`를 실제 ID로 바꾸세요. 새 출력 경로를 지정하세요.
오디오 묶음 길이는 2초부터 30초까지 지정할 수 있습니다. 기본값은 6초입니다.
TUI는 6초 묶음을 사용합니다.

| 시스템 | 입력 | 장치와 권한 |
| --- | --- | --- |
| macOS | AVFoundation 오디오 | 번호나 이름을 선택하세요. 터미널 또는 실행 호스트에 마이크 권한을 허용하세요. |
| Linux | PulseAudio | 소스 ID를 선택하세요. PipeWire에서는 PulseAudio 호환 서비스가 필요합니다. |
| Windows | DirectShow 오디오 | 장치 이름을 선택하세요. `default`는 목록의 첫 마이크입니다. 데스크톱 앱의 마이크 접근을 허용하세요. |

앱은 모델을 로딩한 뒤 마이크를 엽니다.
입력 오디오는 메모리에서 처리합니다. 원본 녹음 파일을 만들지 않습니다.
자막 한 묶음을 완성할 때마다 텍스트 파일을 갱신합니다.
`--output`을 생략하면 현재 폴더에 `live-<시각>.ko.txt`를 만듭니다.
인식한 음성이 없으면 빈 파일이 남을 수 있습니다.

TUI의 `x` 또는 CLI의 `Ctrl+C`로 입력을 중지하세요.
앱은 버퍼에 남은 오디오를 처리한 뒤 종료합니다.
모델 다운로드나 진행 중인 인식 작업 때문에 종료가 늦어질 수 있습니다.
TUI의 `q` → `y`도 버퍼를 처리한 뒤 종료합니다.

입력 대기열은 최대 다섯 묶음을 보관합니다.
인식 속도가 입력을 따라가지 못하면 입력을 중지하고 미처리 오디오가 있다는 오류를 표시합니다.
앱은 이미 완성한 자막을 보존합니다.
작은 모델을 선택하면 처리 시간을 줄일 수 있습니다.
CLI 묶음 길이를 늘리면 반복 처리 비용을 줄일 수 있지만 자막 표시가 늦어집니다.

실시간 자막은 묶음 경계의 단어를 놓칠 수 있습니다.
무음 기준 때문에 작은 목소리를 건너뛸 수 있습니다.
잡음, 겹치는 목소리, 혼합 언어는 잘못된 결과를 만들 수 있습니다.
이 버전은 회의나 장시간 녹음의 정확도를 수치로 보장하지 않습니다.

### 마이크 없이 시험

파일을 원래 시간 흐름에 맞춰 처리하세요.

```bash
whisper-ko live --input "sample.mp3" --language ko --model tiny --output "replay.ko.txt"
```

TUI에서는 파일을 선택하고 `r`을 누르세요.
이 시험은 인식기에 오디오를 전달합니다. 스피커로 소리를 재생하지 않습니다.
파일 시험으로 마이크 권한이나 실제 캡처를 검증할 수는 없습니다.

## 데이터와 모델

앱은 인식과 번역을 로컬에서 실행합니다.
오디오와 결과 텍스트를 업로드하지 않습니다.
패키지 설치 프로그램과 모델 다운로드 클라이언트는 배포 서버에 접속합니다.
해당 서버는 IP 주소 등 일반적인 요청 정보를 받을 수 있습니다.
앱에는 계정이나 API 키가 필요하지 않습니다.

`XDG_CACHE_HOME`을 설정하면 Whisper는 `$XDG_CACHE_HOME/whisper`를 사용합니다.
설정하지 않으면 Windows를 포함해 `~/.cache/whisper`를 사용합니다.
번역 클라이언트의 일반적인 캐시 경로는 `~/.cache/huggingface/hub`입니다.
Hugging Face 환경 설정에 따라 이 경로가 달라질 수 있습니다.

캐시에 있는 모델은 가중치를 다시 다운로드하지 않고 사용할 수 있습니다.
온라인 상태의 Hugging Face 클라이언트는 모델 메타데이터를 확인할 수 있습니다.
캐시한 번역 모델에서 이 요청을 막으려면 `HF_HUB_OFFLINE=1`을 설정하세요.
캐시가 불완전하면 오프라인 실행은 실패합니다.

오디오 파일과 결과는 직접 삭제할 때까지 남습니다.
파일에 개인정보가 들어갈 수 있습니다.
로그나 화면을 공유하기 전에 개인 경로와 텍스트를 지우세요.

## 모델 출처

- [OpenAI Whisper](https://github.com/openai/whisper)는 음성 인식을 제공합니다. 코드와 모델 가중치는 MIT License를 사용합니다.
- [Neurora/opus-hplt-en-ko-v2.0](https://huggingface.co/Neurora/opus-hplt-en-ko-v2.0)는 CC BY 4.0으로 영한 번역을 제공합니다.
- 이 번역 모델은 [HPLT/translate-en-ko-v2.0-hplt_opus](https://huggingface.co/HPLT/translate-en-ko-v2.0-hplt_opus)를 Transformers용으로 변환한 모델입니다.
- 앱은 번역 revision `06f3f7b03a97728560826d7387e1ea25224c65a9`를 고정합니다.

저장소에는 모델 가중치를 포함하지 않습니다.
프로젝트의 MIT License가 모델이나 의존성 라이선스를 대체하지 않습니다.
FFmpeg 라이선스는 설치한 빌드에 따라 다릅니다.
FFmpeg를 재배포하려면 [FFmpeg 라이선스 안내](https://ffmpeg.org/legal.html)를 확인하세요.
시험 오디오의 출처는 `tests/fixtures/`에 별도로 기록합니다.

## 문제 해결

| 증상 | 조치 |
| --- | --- |
| Python 버전 오류 | 3.11 또는 3.12를 설치하세요. 셸 설치 스크립트에서는 `WHISPER_PYTHON`에 Python 경로를 설정하세요. |
| `whisper-ko`를 찾을 수 없음 | 설치 절차의 실행 파일 전체 경로를 사용하거나 해당 폴더를 `PATH`에 추가하세요. |
| FFmpeg를 찾을 수 없음 | FFmpeg를 설치하세요. 설치 중 `PATH`가 바뀌었다면 새 터미널을 여세요. |
| macOS Tk import 오류 | Python과 같은 버전의 Homebrew `python-tk`를 설치하세요. 설치된 실행 파일을 사용하세요. |
| Linux Tk import 오류 | Python과 같은 버전의 Tk 패키지를 설치하세요. |
| Linux 디스플레이 없음 | CLI/TUI를 사용하세요. 진단에는 `doctor --no-gui --tui`를 사용하세요. |
| TUI가 열리지 않음 | 대화형 터미널을 사용하세요. 창을 60열 × 24행 이상으로 늘리세요. |
| Windows curses import 오류 | Windows 설치 절차에 따라 Python 3.11 또는 3.12로 릴리스 wheel을 설치하세요. |
| 설치 체크섬 불일치 | 해당 GitHub 릴리스에서 설치 스크립트를 다시 받으세요. 불일치가 반복되면 보고하세요. |
| 설치 실행 파일 경로가 이미 사용 중임 | 다른 `--bin-dir`를 지정하거나 기존 파일을 확인한 뒤 변경하세요. |
| 설치 스크립트가 `/dev/tty`를 열 수 없음 | 설치는 완료됐습니다. 대화형 터미널에서 출력한 실행 파일 경로를 실행하세요. |
| 결과 파일이 이미 있음 | 새 경로를 지정하세요. 파일 변환에서 교체하려면 명시적으로 확인하세요. |
| 첫 실행이 오래 걸림 | 모델 다운로드와 로딩을 기다리세요. 네트워크와 디스크 여유 공간을 확인하세요. |
| 결과가 비거나 잘못됨 | 음성 언어를 지정하세요. 오디오 크기와 녹음 품질을 확인하세요. |
| 실시간 처리가 느림 | `tiny`를 선택하세요. CPU를 많이 쓰는 다른 프로그램을 닫으세요. |
| 마이크 입력 실패 | 장치 ID와 운영체제 마이크 권한을 확인하세요. |
| Linux 마이크 소스 없음 | 데스크톱 세션에서 PulseAudio 호환 서비스를 실행하세요. `pactl list short sources`를 확인하세요. |

버그를 보고할 때 앱 버전, OS, CPU 아키텍처, Python 버전, 명령, 전체 오류를 적으세요.
모델, 입력 언어, `doctor` 결과도 포함하세요.
공개할 권한이 있는 오디오만 공유하세요.

## 업데이트와 삭제

업데이트하거나 삭제하기 전에 앱을 종료하세요.
필요한 원본 오디오와 결과는 보관하세요.

### macOS와 Linux 릴리스 설치

업데이트하려면 [README](../README.ko.md#설치)의 최신 설치 명령을 다시 실행하세요.
경로를 지정했다면 같은 `--prefix`와 `--bin-dir` 값을 사용하세요.
설치를 완료하면 실행 파일이 새 릴리스 폴더를 사용합니다.
이전에 설치한 버전은 `<prefix>/releases/` 아래에 남습니다.

이전 버전을 지우려면 텍스트 편집기에서 `whisper-ko` 실행 파일을 읽으세요.
그 파일에 적힌 릴리스 폴더는 유지하세요.
더 이상 필요하지 않은 이전 릴리스 폴더만 지우세요.
설치한 릴리스 폴더를 이동하지 마세요. Python 환경이 원래 경로를 사용합니다.

전체 설치를 삭제하려면 `~/.local/bin/whisper-ko`와 `~/.local/share/whisper-local-ko`를 지우세요.
경로를 지정했다면 해당 실행 파일과 데이터 폴더를 지우세요.

### Wheel 설치

업데이트하려면 원하는 릴리스 URL로 wheel 설치 명령을 다시 실행하세요.
같은 Python 환경을 사용하세요.
설치 후 `whisper-ko --version`과 `whisper-ko doctor --no-gui --tui`를 확인하세요.

활성화한 환경에서 다음 명령으로 패키지를 삭제하세요.

```sh
python -m pip uninstall whisper-local-ko
```

위의 Windows 설치를 삭제하려면 앱을 종료한 뒤 전용 `%LOCALAPPDATA%\whisper-local-ko` 폴더를 지우세요.
다른 전용 환경을 사용했다면 앱을 종료한 뒤 해당 환경 폴더를 지우세요.

### 소스 설치

결과를 백업하세요.
저장소를 원하는 릴리스로 갱신하세요. 설치 스크립트를 다시 실행하세요.
직접 수정한 소스를 확인 없이 덮어쓰지 마세요.
앱을 종료한 뒤 전용 `.venv`를 지울 수 있습니다.

이 삭제 절차는 모델, 시스템 Python, Tk, FFmpeg를 지우지 않습니다.
더 이상 사용하지 않는 모델 캐시 폴더만 지우세요.
다른 앱이 같은 캐시를 사용할 수 있습니다.
