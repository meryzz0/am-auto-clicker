#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf '[1/6] Python unit and project-integrity tests…\n'
PYTHONPATH="$ROOT/src" python3 -m unittest discover -s tests -v
printf '\n[2/6] Python syntax…\n'
python3 -m compileall -q src tests
printf 'Python sources compile.\n'
printf '\n[3/6] Installer syntax…\n'
bash -n install.sh
bash -n uninstall.sh
bash -n scripts/check.sh
printf 'Shell scripts parse.\n'
printf '\n[4/6] Embedded installer snippets…\n'
python3 - <<'PY'
import pathlib
import re

for filename in ("install.sh", "uninstall.sh"):
    lines = pathlib.Path(filename).read_text(encoding="utf-8").splitlines()
    index = 0
    blocks = 0
    while index < len(lines):
        match = re.match(r"(?:if\s+!\s+)?python3 - .*<<'([^']+)'", lines[index].strip())
        if not match:
            index += 1
            continue
        delimiter = match.group(1)
        end = index + 1
        body = []
        while end < len(lines) and lines[end].strip() != delimiter:
            body.append(lines[end])
            end += 1
        if end >= len(lines):
            raise SystemExit(f"{filename}: unterminated heredoc {delimiter}")
        compile("\n".join(body), f"{filename}:embedded-python-{blocks + 1}", "exec")
        blocks += 1
        index = end + 1
    print(f"{filename}: {blocks} embedded Python block(s) compile")
PY
printf '\n[5/6] CLI smoke test (without importing GTK)…\n'
PYTHONPATH="$ROOT/src" python3 -m am_auto_clicker --version
PYTHONPATH="$ROOT/src" python3 -m am_auto_clicker --help >/dev/null
printf 'CLI entry point responds.\n'
printf '\n[6/6] Optional ShellCheck…\n'
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck install.sh uninstall.sh scripts/check.sh
else
  printf 'ShellCheck is not installed; syntax checks above were completed.\n'
fi
