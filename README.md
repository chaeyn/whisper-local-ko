# 로컬 Whisper 한국어 변환기

한국어 GUI에서 M4A 오디오를 열어 한국어 텍스트로 바꿉니다. 한국어 음성은 Whisper로 받아쓰고, 영어 음성은 Whisper로 받아쓴 뒤 영한 번역 모델로 한국어화합니다. 모델 파일을 처음 내려받을 때만 인터넷이 필요하며, 오디오 파일은 온라인 서비스로 전송하지 않습니다.

## 설치 및 실행 (macOS, Homebrew Python 3.14)

현재 Homebrew Python 3.14에는 Tkinter가 별도 패키지로 제공됩니다. 아래 명령은 기존 가상 환경을 유지하며 Tkinter와 번역 패키지를 추가합니다.

```bash
brew install ffmpeg python-tk@3.14
export PYTHONPATH="$(brew --prefix python-tk@3.14)/libexec${PYTHONPATH:+:$PYTHONPATH}"
python -c "import tkinter; print('Tkinter OK')"
python -m pip install -r requirements.txt
python whisper_m4a.py
```

명령을 실행하기 전에 이 폴더로 이동하고, 기존 `.venv`를 활성화하세요. Tkinter 확인 명령에서 `Tkinter OK`가 나오면 앱을 실행할 수 있습니다. Python 버전이 3.14가 아니라면 `python-tk@3.14`를 현재 Python의 주·부 버전에 맞춰 바꾸세요.

첫 실행 때 선택한 Whisper 모델과 영한 번역 모델을 내려받습니다. 다음 실행부터 모델을 로컬에서 사용합니다. FFmpeg는 M4A 오디오를 읽는 데 필요합니다.

## 사용법

1. **파일 선택**을 누르고 M4A 파일을 고릅니다.
2. 음성 언어를 고릅니다. 잘 모르면 **자동 감지**를 선택하세요.
3. Whisper 모델을 선택하고 **변환 시작**을 누릅니다.
4. 결과가 앱 창에 표시되고, 원본 파일과 같은 폴더에 `<파일명>.ko.txt`로 저장됩니다.

`tiny`와 `base`는 빠르고 가벼우며, `small`은 속도와 인식 품질의 균형을 제공합니다. `medium`과 `large`는 더 많은 메모리와 처리 시간이 필요합니다. 기본값은 `small`입니다.

Whisper는 공개 음성 인식 모델입니다. 영어를 한국어로 바꿀 때 쓰는 `Helsinki-NLP/opus-mt-tc-big-en-ko`는 별도로 내려받아 로컬에서 실행합니다. 다른 언어가 감지되면 Whisper가 영어로 옮긴 뒤 한국어로 번역합니다. 문맥에 따라 인식이나 번역이 틀릴 수 있으므로 결과를 확인하세요.

## 모델 출처

- OpenAI Whisper: MIT License
- Helsinki-NLP OPUS-MT 영어-한국어 모델: CC-BY-4.0

모델 카드와 사용 예제는 [Helsinki-NLP/opus-mt-tc-big-en-ko](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-ko)를 참고하세요.
