"""Verifica que los links relativos de los archivos Markdown apunten a archivos existentes."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIPPED_DIRS = {".git", ".venv"}


def find_broken_links(root: Path) -> list[str]:
    errors = []
    for md in sorted(root.rglob("*.md")):
        if SKIPPED_DIRS.intersection(md.relative_to(root).parts):
            continue
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for target in LINK.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path = unquote(target.split("#", 1)[0])
                if path and not (md.parent / path).exists():
                    errors.append(f"{md.relative_to(root)}:{lineno}: link roto -> {target}")
    return errors


def main() -> int:
    errors = find_broken_links(ROOT)
    if errors:
        print("\n".join(errors))
        return 1
    print("Todos los links relativos son válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
