# Testing

[Contributing](../CONTRIBUTING.md) · [Recorded results](../VALIDATION.md)

Test the changed behavior and its failure paths.
Record what ran. Distinguish an intended CI job from a completed job.

## Fast checks

Run from the repository root in an active development environment:

```bash
python -m unittest discover -s tests -v
python -m pip check
python -m ruff check .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_docs.py
```

Most tests use fake recognizers and temporary output folders.
They check saved text, result protection, errors, TUI state, buffering, and platform commands.
They do not establish speech accuracy.
An opt-in model test can be skipped in the default unit run.
State the pass and skip counts in the test record.

## Real-model checks

Use the licensed Korean sample in `tests/fixtures/`.
Read its attribution before you reuse or distribute it.
Run the opt-in suite on macOS or Linux:

```bash
WHISPER_INTEGRATION=1 python -m unittest discover -s tests -p test_integration.py -v
```

On PowerShell, set the variable before the same test command:

```powershell
$env:WHISPER_INTEGRATION = "1"
python -m unittest discover -s tests -p test_integration.py -v
Remove-Item Env:WHISPER_INTEGRATION
```

A clean machine needs to download the `tiny` model.

Also test English speech when you change recognition or translation.
Compare the saved Korean text with the intended meaning.
A nonempty file is insufficient evidence.
Record the model name, translation revision, sample source, and observed errors.

## Package installation

Build and prepare the assets from the intended release commit:

```sh
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/prepare_release.py
```

Check the wheel, source archive, version-matched `install.sh`, and `SHA256SUMS.txt` in `dist/`.
The manifest covers the wheel, source archive, and installer.
The preparation script does not publish these files.

Create a clean Python 3.11 or 3.12 environment outside the source tree.
Install that wheel with its dependencies.
Run the installed command from a different directory.
Check version, help, `doctor --no-gui --tui`, and a file conversion.
This catches missing package files and accidental source-tree imports.

## Release installer checks

Test the standalone `install.sh` separately from source setup.
Use a temporary prefix and launcher folder so the test preserves the user's installed app.

Check these paths before publication:

- Parse the script with `sh -n` and `dash -n`.
- Read `--help` with `sh`, `dash`, and piped script input.
- Install into a path with spaces without a Git checkout.
- Verify the source archive checksum before setup runs.
- Reject a mismatched checksum and unsafe archive paths.
- Keep the previous launcher and installation when download or setup fails.
- Keep an unrelated file at the requested launcher path.
- Replace a managed launcher only after the new installation passes its checks.
- Run the launcher from outside the installation folder and check relative input paths.
- Confirm that installation does not edit shell profiles.
- Use a real terminal to test piped installation with `--run` and TUI exit.
- Confirm that `--run` without a terminal reports the launch error and keeps the completed installation.

After publication, run the documented commands against the GitHub release assets.
Check both the versioned installer URL and the `releases/latest/download/install.sh` URL.
Test the release wheel URL in a fresh Windows environment.
Record each environment, resolved release version, commands, and result.
Tests with simulated downloads do not prove that published assets are available.

## Terminal and GUI checks

Use a real interactive terminal for these checks:

1. Start the TUI with no command arguments.
2. Open the file browser.
3. Select a path with spaces or Korean characters.
4. Run a short conversion.
5. Observe progress and the final saved path.
6. Repeat the conversion to check replacement confirmation.
7. Cancel the replacement and confirm that the file is unchanged.
8. Run file replay to check incremental captions.
9. Stop replay while input is active.
10. Check the saved text and terminal state after exit.

For GUI changes, open a real Tk window.
Check file selection, settings, start, error display, result display, and close behavior.
Run Tk import checks separately from window and user-flow checks.

## Microphone checks

Microphone tests require a person and a physical device.
Do not start recording as part of an unattended test suite.

1. List devices on the target operating system.
2. Select the intended microphone.
3. Allow microphone access when the operating system requests it.
4. Start a new session with a new output path.
5. Speak a known Korean phrase.
6. Check the caption and saved text.
7. Stop input while capture is active.
8. Check that capture ends and completed text remains.

Record the OS, microphone, Python version, model, and result.
Repeat in English when you need to verify live translation.
Device listing and file replay do not prove physical microphone capture.

## CI and release evidence

The workflow targets macOS ARM64, Linux x86_64, and Windows x86_64.
It checks Python 3.11 and 3.12.
The Python 3.11 jobs also run real Korean model inference.
CI does not verify physical microphones or desktop interactions.

The [release installation workflow](../.github/workflows/release-install.yml) runs after publication.
It downloads release assets without a repository checkout.
It checks shell installation on macOS and Linux, and wheel installation on Windows.
Each job uses Python 3.11 and checks the installed version and dependencies.
Use its run conclusion to confirm the published download paths.

Keep exact run links and results in [VALIDATION.md](../VALIDATION.md).
Document failures and untested environments before publishing a release.
