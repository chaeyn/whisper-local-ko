"""Check local Markdown links without network access."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
files = list(ROOT.glob('*.md')) + list((ROOT / 'docs').glob('**/*.md')) + list((ROOT / 'tests').glob('**/*.md'))
errors = []
for path in files:
    text = path.read_text(encoding='utf-8')
    for match in re.finditer(r'(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
        target = match.group(1).strip('<>')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        if not (path.parent / unquote(parsed.path)).exists():
            errors.append(f'{path.relative_to(ROOT)}: missing {target}')
    if '/Users/' in text:
        errors.append(f'{path.relative_to(ROOT)}: contains an absolute home path')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Checked local links in {len(files)} Markdown files.')
