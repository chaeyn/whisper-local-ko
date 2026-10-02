# Third-party notices

The application code uses the [MIT License](LICENSE).
Dependencies and model weights keep their own licenses.
Package installers obtain dependencies from their distributors.
The release does not include model weights or FFmpeg binaries.

| Component | Author or project | License | Use |
| --- | --- | --- | --- |
| [Whisper](https://github.com/openai/whisper) | OpenAI | MIT | Speech recognition code and model weights |
| [PyTorch](https://github.com/pytorch/pytorch/blob/main/LICENSE) | PyTorch contributors | BSD-style license | Model execution |
| [Transformers](https://github.com/huggingface/transformers/blob/main/LICENSE) | Hugging Face contributors | Apache-2.0 | Translation model execution |
| [SentencePiece](https://github.com/google/sentencepiece/blob/master/LICENSE) | Google and contributors | Apache-2.0 | Text processing |
| [Sacremoses](https://github.com/hplt-project/sacremoses/blob/master/LICENSE) | Sacremoses contributors | MIT | Text processing |
| [Filelock](https://github.com/tox-dev/filelock/blob/main/LICENSE) | Filelock contributors | MIT | Model download lock |
| [windows-curses](https://github.com/zephyrproject-rtos/windows-curses) | windows-curses contributors | Python Software Foundation license | Windows terminal UI |
| [FFmpeg](https://ffmpeg.org/legal.html) | FFmpeg developers | LGPL or GPL, depending on build options | Audio decoding and capture |

## English-to-Korean model

The app uses [Neurora/opus-hplt-en-ko-v2.0](https://huggingface.co/Neurora/opus-hplt-en-ko-v2.0).
Neurora converted the [HPLT model](https://huggingface.co/HPLT/translate-en-ko-v2.0-hplt_opus) for Transformers.
The model card specifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The app uses revision `06f3f7b03a97728560826d7387e1ea25224c65a9` without changes to the weights.
Credit HPLT and Neurora when you redistribute these weights.

## Test audio

The source archive includes one audio fixture by masterTOPIK under CC BY 3.0.
See the [fixture attribution](tests/fixtures/README.md).
The application wheel does not include the fixture.

Review the license files of installed transitive dependencies before you redistribute a complete runtime.
