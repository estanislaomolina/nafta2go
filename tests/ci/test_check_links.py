"""Tests del verificador de links relativos que corre en CI."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "check_links.py"
spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
check_links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_links)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_valid_relative_links_have_no_errors(tmp_path):
    write(tmp_path / "docs" / "PRD.md", "# PRD")
    write(tmp_path / "README.md", "[PRD](docs/PRD.md) y [sección](docs/PRD.md#problema)")
    assert check_links.find_broken_links(tmp_path) == []


def test_broken_link_is_reported_with_file_and_line(tmp_path):
    write(tmp_path / "README.md", "título\n\n[falta](docs/NO_EXISTE.md)\n")
    assert check_links.find_broken_links(tmp_path) == [
        "README.md:3: link roto -> docs/NO_EXISTE.md"
    ]


def test_external_links_and_anchors_are_ignored(tmp_path):
    write(
        tmp_path / "README.md",
        "[web](https://x.org) [http](http://x.org) [mail](mailto:a@b.c) [ancla](#seccion)",
    )
    assert check_links.find_broken_links(tmp_path) == []


def test_url_encoded_paths_are_resolved(tmp_path):
    write(tmp_path / "docs" / "Propuesta nafta2go.md", "x")
    write(tmp_path / "README.md", "[propuesta](docs/Propuesta%20nafta2go.md)")
    assert check_links.find_broken_links(tmp_path) == []


def test_virtualenv_and_git_dirs_are_skipped(tmp_path):
    write(tmp_path / ".venv" / "lib" / "README.md", "[roto](no-existe.md)")
    write(tmp_path / ".git" / "README.md", "[roto](no-existe.md)")
    assert check_links.find_broken_links(tmp_path) == []


def test_links_resolve_relative_to_each_file(tmp_path):
    write(tmp_path / "adr" / "README.md", "[formato](ADR-Format.md) [raíz](../README.md)")
    write(tmp_path / "adr" / "ADR-Format.md", "x")
    write(tmp_path / "README.md", "x")
    assert check_links.find_broken_links(tmp_path) == []
