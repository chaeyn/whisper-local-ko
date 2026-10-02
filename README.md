# Whisper on Mac

M4A·MP3·WAV 음성을 한국어 텍스트로 저장하는 로컬 프로그램입니다. 한국어 음성은 OpenAI Whisper로 받아쓰고, 영어 음성은 받아쓴 뒤 OPUS-MT 영한 모델로 번역합니다. 한국어 GUI와 CLI를 제공합니다.

오디오와 인식한 문장은 외부 서비스로 보내지 않습니다. 패키지 설치와 모델 첫 다운로드에는 인터넷이 필요합니다. 모델 다운로드 과정에서 모델 제공 서버에 접속하며, 다운로드한 모델은 사용자 캐시에 보관합니다. 계정이나 API 키는 필요하지 않습니다.

## 처음 설치

macOS와 [Homebrew](https://brew.sh)가 필요합니다. 이 폴더를 내려받거나 복사한 뒤 터미널에서 실행하세요. 경로에 공백이 있으면 따옴표로 감싸세요.

```bash
cd /설치한/경로/whisper-on-mac
./scripts/setup.sh
./scripts/run.sh
```

설치 스크립트는 Homebrew Python 3.11, 해당 버전의 Tkinter, FFmpeg를 설치하고 이 폴더의 `.venv`에 고정 버전 패키지를 설치합니다. 마지막에 환경 진단을 실행합니다. 기존 `.venv`가 다른 Python 버전이면 중단하므로 폴더 이름을 바꿔 보존한 뒤 다시 실행하세요.

Python 3.11을 검증 기준으로 사용합니다. 기존 Homebrew Python 3.14 가상환경에 패키지를 추가하는 방식 대신 위 설치 절차로 별도 환경을 만드세요. 모델 파일과 가상환경은 저장소에 포함하지 않습니다. Apple Silicon에서 실행을 확인했으며 Intel Mac은 확인하지 않았습니다.

## GUI 사용

1. **파일 선택**에서 오디오를 고릅니다.
2. 음성 언어는 **자동 감지**, **한국어**, **영어** 중 선택합니다. 짧은 음성의 언어를 잘못 감지하면 직접 선택하세요.
3. 모델을 고르고 **변환 시작**을 누릅니다. 기본값은 `small`이며 첫 시험에는 `tiny`를 사용할 수 있습니다. 큰 모델은 메모리와 시간이 더 필요합니다.
4. 결과를 창에서 확인합니다. 원본 옆에 `<파일명>.ko.txt`가 UTF-8로 저장됩니다. 기존 결과가 있으면 교체 여부를 묻습니다.

첫 변환은 Whisper 모델을 내려받습니다. 영어 음성은 영한 모델도 내려받으므로 다운로드 시간과 디스크 공간이 더 필요합니다. CPU로 처리하며 실행 중 앱을 닫으면 작업이 중단됩니다. 오류가 나오면 파일 경로, 여유 공간, 인터넷 연결과 환경 진단 결과를 확인하세요.

자동 감지에서 한국어·영어 외의 언어가 나오면 변환을 중단합니다. 인식·번역 품질은 음질과 발화에 따라 달라지므로 저장된 텍스트를 확인하세요. 앱 창에서 텍스트를 편집해도 저장 파일에는 반영하지 않습니다.

## CLI와 환경 진단

```bash
./scripts/run.sh doctor
./scripts/run.sh doctor --no-gui
./scripts/run.sh transcribe "/경로/회의.m4a" --language ko --model small
./scripts/run.sh transcribe "/경로/interview.m4a" --language en --model tiny --output "/경로/인터뷰.ko.txt"
```

`--language auto`가 기본값입니다. `--output`을 생략하면 원본 옆에 저장합니다. CLI는 결과 파일이 있으면 중단합니다. 교체할 때만 `--overwrite`를 붙이세요. 결과 폴더는 미리 만들어야 합니다. 성공하면 종료 코드 0, 실패하면 1을 반환합니다.

`doctor`는 Python 경로, Whisper·PyTorch·번역 패키지 import, FFmpeg, 실제 Tk 창 생성·종료를 검사합니다. 모델 다운로드나 음성 인식 품질은 검사하지 않습니다. `--no-gui`는 Tk 검사만 생략합니다. CLI는 Tkinter 없이도 사용할 수 있습니다.

Tkinter 오류가 나면 `brew install python-tk@3.11` 후 `scripts/run.sh`로 실행하세요. 이 실행 스크립트는 Homebrew Tkinter의 `libexec` 경로를 연결합니다. 터미널의 `python`을 직접 쓰면 다른 Python 환경에서 실행할 수 있습니다. FFmpeg 오류는 `brew install ffmpeg`로 해결합니다. 패키지 오류는 `scripts/setup.sh`를 다시 실행하세요.

## 개발과 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

`requirements.in`은 직접 사용하는 패키지, `requirements.txt`는 macOS Python 3.11용 고정 버전 목록입니다. 변경 시 `uv pip compile requirements.in --python-version 3.11 -o requirements.txt`로 갱신하고 설치·변환을 재확인하세요. 다른 운영체제를 위한 lock 파일은 아닙니다.

테스트는 한국어 저장, 영어 번역 경로, 기존 결과 보호, 원본 보호, 빈 결과·지원하지 않는 언어 처리, 긴 번역 텍스트 분할을 검사합니다. 실제 설치·모델·오디오 검증 결과는 [VALIDATION.md](VALIDATION.md)에 기록합니다. 사용자 오디오와 결과, 모델, `.venv`, 임시 검증 파일은 Git에서 제외합니다.

## 모델 출처

- [OpenAI Whisper](https://github.com/openai/whisper): 코드와 모델 MIT License. FFmpeg로 오디오를 읽고 로컬에서 인식합니다.
- [Helsinki-NLP/opus-mt-tc-big-en-ko](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-ko): 영한 번역 모델, CC-BY-4.0. Transformers의 Marian 모델 클래스로 실행합니다.

이 프로젝트 자체의 재배포 라이선스는 아직 지정하지 않았습니다. 공개 배포 시 프로젝트 라이선스를 정하고 모델·의존성의 라이선스를 함께 확인하세요.
