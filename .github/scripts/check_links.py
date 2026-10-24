"""Verifica que los links relativos de los archivos Markdown apunten a archivos existentes."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

errors = []
for md in sorted(ROOT.rglob("*.md")):
    if ".git" in md.parts or ".venv" in md.parts:
        continue
    for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = unquote(target.split("#", 1)[0])
            if path and not (md.parent / path).exists():
                errors.append(f"{md.relative_to(ROOT)}:{lineno}: link roto -> {target}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("Todos los links relativos son válidos.")
