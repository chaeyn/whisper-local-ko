# 실행 검증 기록

2026-10-02, macOS Apple Silicon, Homebrew Python 3.11.17에서 확인했습니다.

## 통과

- 새 `.venv`에서 `scripts/setup.sh` 실행: 고정 패키지 설치와 최종 doctor 통과.
- `scripts/run.sh doctor`: Whisper·PyTorch·Transformers·SentencePiece·Sacremoses import, FFmpeg, Tk 창 생성·종료 통과.
- `python -m pip check`: 의존성 충돌 없음.
- 단위 테스트 7개 통과: 한국어 UTF-8 저장, 영어 번역 경로, 기존 결과·원본 보호, 빈 결과·지원하지 않는 언어 거부, 덮어쓰기, 긴 텍스트 분할, 공개 모델 인증 미사용.
- 앱 GUI 초기화와 이벤트 루프 실행·종료 통과. 실제 영어 M4A를 GUI 변환 함수로 시작해 worker·이벤트 큐·완료 처리를 거친 후, 창의 표시 텍스트와 저장 파일이 일치함을 확인했습니다. 파일 선택창을 수동 클릭하는 시험은 하지 않았습니다.
- 없는 파일의 CLI 요청: 이해할 수 있는 오류와 종료 코드 1 확인.
- 한국어·영어 합성 음성을 FFmpeg로 M4A로 만든 뒤 실제 로컬 모델로 변환하고 저장했습니다. 사용자 오디오는 사용하지 않았습니다.

한국어 원문(macOS Yuna):

> 안녕하세요. 오늘 회의에서는 프로젝트 일정과 다음 주 계획을 이야기합니다.

Whisper `small` 저장 결과:

> 안녕하세오 오늘 회의에서는 프로젝트 일정과 다음 주 계획을 이야기 합니다.

영어 원문(macOS Samantha):

> Hello. Today we will discuss the project schedule and our plans for next week.

Whisper `small` + OPUS/HPLT 저장 결과:

> 안녕하세요, 오늘 우리는 프로젝트 일정과 다음 주에 대한 계획에 대해 논의할 것입니다.

## 발견하고 수정한 문제

- 기존 `Helsinki-NLP/opus-mt-tc-big-en-ko`는 정상 영어 문장에도 의미가 맞지 않는 결과를 냈습니다. 음성 인식 단계와 직접 텍스트 번역을 따로 검사해 번역 모델에서 발생함을 확인했습니다. [원본 프로젝트 이슈 #81](https://github.com/Helsinki-NLP/OPUS-MT-train/issues/81)에도 같은 모델의 문제 보고가 있습니다.
- 실제 문장 번역을 통과한 `Neurora/opus-hplt-en-ko-v2.0`로 교체하고 모델 revision을 고정했습니다. [변환 모델](https://huggingface.co/Neurora/opus-hplt-en-ko-v2.0), [원본 HPLT 모델](https://huggingface.co/HPLT/translate-en-ko-v2.0-hplt_opus)을 출처로 사용합니다.
- 공개 Hugging Face 모델 다운로드에 기존 인증이 개입해 실패했습니다. `token=False`로 공개 요청을 사용합니다.
- Whisper 첫 다운로드를 동시에 시작했을 때 SHA256 검사 실패를 확인했습니다. 같은 모델의 다운로드·로딩 구간에 파일 잠금을 적용했습니다. 적용 후 동시 첫 다운로드를 다시 시험하지는 않았습니다.

## 검증 한계

합성 문장 몇 개의 실행·저장 검증입니다. 사용자 녹음, 잡음, 긴 회의, 혼합 언어, Intel Mac, 다른 macOS 버전은 확인하지 않았습니다. `tiny`에서 한국어 오인식이 커졌고 `small`에서도 철자 오류가 남았습니다. 정량적인 인식·번역 정확도나 처리속도는 측정하지 않았습니다.

검증용 오디오, 출력과 로그는 Git에서 제외한 `work/`에만 보관했습니다. 모델은 사용자 캐시에 저장하며 Git에 포함하지 않습니다. GitHub 생성·push는 수행하지 않았습니다.
