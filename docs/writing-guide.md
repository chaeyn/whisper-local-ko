# Writing guide

## Scope

The project uses a writing style inspired by [ASD-STE100](https://www.asd-ste100.org/about_STE.html).
The standard defines English writing rules and a controlled dictionary.
This project applies selected clarity principles to English and Korean.
It does not claim full dictionary compliance, formal conformance, or certification.
The Korean rules below are project rules. They are not an official Korean STE standard.

## English rules

- Give each instruction one action.
- Start instructions with a verb.
- State a condition before the action that depends on it.
- Use active voice and name the actor when needed.
- Keep one term for one concept.
- Use short sentences. Aim for 20 words or fewer in instructions.
- Aim for 25 words or fewer in descriptions.
- Keep commands, code identifiers, paths, and exact UI labels unchanged.
- State the expected result after a procedure.
- Describe errors with a cause and an action the user can take.
- Separate verified results from planned work and untested behavior.
- Avoid idioms, promotional claims, em dashes, and rhetorical questions.

These length targets are editorial checks. They do not replace a review for accuracy.
Do not split a sentence if the split makes the instruction ambiguous.
Do not describe a model as accurate without a stated sample and measurement.

## 한국어 작성 원칙

영문 문서와 같은 동작, 조건, 검증 범위를 설명하세요.
한국어에는 위 영어 단어 수 기준을 기계적으로 적용하지 않습니다.

- 한 지시문에 하나의 행동을 적으세요.
- 사용 절차는 `선택하세요`, `실행하세요`, `확인하세요`처럼 직접 쓰세요.
- 조건을 먼저 적고 해당 행동을 설명하세요.
- 행동 주체가 필요하면 사용자, 앱, 관리자를 구체적으로 쓰세요.
- 같은 개념에는 같은 용어를 쓰세요.
- 한 문장이 길어지면 행동이나 조건 단위로 나누세요.
- 명령, 코드 식별자, 경로, 실제 화면 표시는 보존하세요.
- 절차 뒤에 예상 결과를 적으세요.
- 오류 설명에는 원인과 사용자가 할 조치를 적으세요.
- 확인한 결과와 계획, 미검증 항목을 구분하세요.
- 관용구, 홍보 문구, em dash, 수사적 질문을 빼세요.

직역 때문에 동작이 모호해지면 자연스러운 한국어로 고치세요.
시험한 자료와 측정값 없이 모델의 정확도를 평가하지 마세요.

## Glossary

| English term | Korean term | Meaning |
| --- | --- | --- |
| source audio | 원본 오디오 | The input recording |
| transcript | 받아쓰기 결과 | Text recognized from speech |
| result | 결과 | Korean text after recognition and optional translation |
| output path | 출력 경로 | The destination text file path |
| model | 모델 | Downloaded recognition or translation weights |
| chunk | 오디오 묶음 | A fixed-duration part of live input |
| buffer | 버퍼 | Audio held until processing |
| live captions | 실시간 자막 | Captions added after each processed chunk |
| file replay | 파일 시험 | File input processed at its normal time rate |
| replace | 교체 | Write a new completed result over an existing result |
| stop | 중지 | End input or processing as described for the selected mode |
| verified | 검증 완료 | A stated check passed in the recorded environment |
| unverified | 미검증 | The stated check has not established the behavior |

## Review examples

| Use | Reason |
| --- | --- |
| `Select a new output path.` / `새 출력 경로를 선택하세요.` | One action with the same meaning in both languages |
| `If the file exists, select Replace.` / `파일이 있으면 Replace를 선택하세요.` | Condition before action; exact UI label preserved |
| `The unit tests passed. Microphone capture is unverified.` / `단위 시험을 통과했습니다. 마이크 캡처는 미검증입니다.` | Evidence and limits stated separately |

Update both language versions when behavior changes.
Review links, commands, default values, and glossary terms before publication.
