# Contributing

[한국어](CONTRIBUTING.ko.md) · [Architecture](docs/architecture.md) · [Writing guide](docs/writing-guide.md)

We accept bug reports, reproducible test cases, documentation changes, translations, and pull requests.
Use English or Korean in issues and pull requests.
The main documentation and interface use English.
Keep the Korean introduction and user instructions consistent with the English documents.

## Before you start

Read the [Code of conduct](CODE_OF_CONDUCT.md).
Use [private security reporting](SECURITY.md) for vulnerabilities.
For a large feature or dependency change, open an issue before implementation.
A small fix or documentation correction can go directly to a pull request.

Maintainers review contributions as time permits.
A report or pull request does not guarantee a merge or a release date.

## Set up a development environment

1. Install Git and the prerequisites in the [README](README.md#install).
2. Fork the repository on GitHub.
3. Clone your fork.
4. Create a branch from `main`.
5. Use the commands below to install a virtual environment and development dependencies for your OS.

The release installer in the README is for app users.
Use a source checkout for development.
The setup scripts can create `.venv` and install the runtime dependencies first.

On macOS or Linux, run from the repository root:

```sh
sh scripts/setup.sh
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows PowerShell, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
& ".\.venv\Scripts\python.exe" -m pip install -e '.[dev]'
$env:Path = "$PWD\.venv\Scripts;$env:Path"
```

These commands put the development environment on `PATH` for the current terminal.
The editable installation uses your current source files.
Run `whisper-ko doctor --no-gui --tui` to check that environment.

## Change the code

Keep each change focused on one problem.
Preserve the source audio and existing-result protection.
Keep the TUI responsive while recognition runs.
Keep GUI calls on the main thread.
Use the platform helpers for device selection and model locks.

Add a test when a change affects output, error handling, process lifetime, or platform behavior.
A test should fail for the reported bug before the fix.
Use temporary folders for test outputs.
Do not download models in unit tests.
Do not open a real microphone in automated tests.

Use fixtures with a clear license and attribution.
Keep personal audio, transcripts, tokens, model weights, and environment folders out of commits.
If an AI tool helps with a change, inspect its output and run the required tests yourself.
You are responsible for the submitted behavior and explanation.

## Run checks

Run these commands from the repository root:

```bash
python -m unittest discover -s tests -v
python -m pip check
python -m ruff check .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_docs.py
```

Install the built wheel in a clean environment before a release.
Run `whisper-ko --version` and `whisper-ko doctor --no-gui --tui` there.
Read [Testing](docs/testing.md) for real-model checks and UI checks.
Read [VALIDATION.md](VALIDATION.md) for recorded release evidence.

CI covers the supported OS and Python combinations.
A green unit-test job does not verify a physical microphone or a desktop interaction.
Report those tests separately.

## Change dependencies or models

`pyproject.toml` defines the runtime dependencies and optional development tools.
The requirements files delegate to the project installation.
They are not a transitive dependency lock for each platform.

For a dependency change, check installation on each supported OS.
Use a new virtual environment to detect missing dependencies.
Check wheel availability for both supported Python versions.
Review the dependency license.

For a model change, record its source, license, and immutable revision.
Run real Korean recognition and English-to-Korean translation checks.
Preserve the audio source and expected meaning in the test record.
A successful import or nonempty result does not establish translation quality.

## Write a bug report

Use the [issue form](https://github.com/chaeyn/whisper-local-ko/issues/new/choose).
Include:

- App version or commit.
- OS version, CPU architecture, and Python version.
- The command or key sequence.
- Model, language, input duration, and file format.
- Expected result and actual result.
- Complete error text and the `doctor` result.
- A small reproducible sample, if you can publish it.

Remove private file paths, transcript text, and credentials before submission.
Stay available for follow-up questions.

## Submit a pull request

1. Run the relevant checks.
2. Update the affected user instructions.
3. Check the English and Korean terms against the [glossary](docs/writing-guide.md#glossary).
4. Describe the original problem and the new behavior.
5. List the tests you ran and their results.
6. State which platforms or devices you did not test.
7. Link the related issue, if one exists.

Include a short terminal recording or screenshot when it helps explain a UI change.
Remove personal paths and text from it.
Keep generated packages and local verification outputs out of the pull request.

Submitting a contribution means that you permit its distribution under the project's [MIT License](LICENSE).
Third-party fixtures keep their stated licenses.

## Release checklist

Prepare the release files from the intended release commit:

```sh
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/prepare_release.py
```

The preparation script copies the version-matched `install.sh` into `dist/`.
It creates `SHA256SUMS.txt` for the wheel, source archive, and installer.
Upload these four assets together. The script does not publish them.

Maintainers use this checklist before they publish a release:

- Update the version and release notes.
- Run the supported CI matrix on the release commit.
- Run the real-model checks described in [Testing](docs/testing.md).
- Install and check the wheel in a clean environment.
- Test `install.sh` with `sh` and `dash`, including input from a pipe.
- Check checksum failures, failed updates, paths with spaces, and launcher conflicts.
- Test the documented no-clone commands against the release assets.
- Publish `install.sh`, the source archive, the wheel, and `SHA256SUMS.txt` together.
- Keep the version in `install.sh` consistent with the release tag and package version.
- Check TUI start, file selection, progress, result protection, and exit.
- Record physical microphone checks separately, or state that they are unverified.
- Check documentation links, model attribution, and package contents.
- Review the commit history and release files for private data.
- Update `VALIDATION.md` with the environment, commands, results, and limits.
- Publish the tag and GitHub release after these checks pass.
