# Security policy

## Supported versions

The latest `0.1.x` release receives security fixes when the maintainer can provide them.
Earlier versions do not have a separate maintenance branch.
This project does not provide a response-time guarantee.

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/chaeyn/whisper-local-ko/security/advisories/new).
Describe the affected version, required conditions, impact, and reproduction steps.
Use a small test file that you can share legally.
Remove credentials, private audio, and personal transcripts.

If private reporting is unavailable, open an issue that requests a private contact method.
Do not include vulnerability details in that public issue.

The maintainer will review the report and discuss a fix and disclosure timing with you.
Keep exploit details private until a fix or coordinated disclosure is ready.

## Data and local execution

The app processes audio and text on the local computer.
It uses FFmpeg to decode media and download clients to obtain model weights.
A decoder, model loader, or dependency can still contain vulnerabilities.
Keep system packages and project dependencies current within the supported versions.

Do not run the app with administrator privileges.
Use files from sources you trust.
Use a local output folder that you control.
Review [data and model handling](docs/user-guide.md#data-and-models) before you share diagnostics.

## 한국어 안내

최신 `0.1.x` 버전에 보안 수정을 제공합니다. 대응 시간을 보장하지는 않습니다.
[GitHub 비공개 취약점 신고](https://github.com/chaeyn/whisper-local-ko/security/advisories/new)를 사용하세요.
영향받는 버전, 발생 조건, 영향, 재현 절차를 적으세요.
인증 정보, 개인 오디오, 개인 결과를 제외하세요.

비공개 신고가 열리지 않으면 공개 이슈에서 비공개 연락 방법을 요청하세요.
공개 이슈에는 취약점 세부 내용을 넣지 마세요.
관리자는 신고자와 수정 및 공개 시점을 협의합니다.
앱은 일반 사용자 권한으로 실행하세요.
