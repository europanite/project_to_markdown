import importlib
import runpy
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent

CANDIDATE_PATHS = [
    THIS_DIR / "project_to_markdown.py",  
    REPO_ROOT / "project_to_markdown.py", 
]

def load_module_and_get_main():
    for path in CANDIDATE_PATHS:
        if path.exists():
            mod_dict = runpy.run_path(str(path))
            main = mod_dict.get("main")
            assert callable(main), "main() not found in project_to_markdown.py"
            return main

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("project_to_markdown")
        return getattr(mod, "main")
    except Exception as e:
        raise FileNotFoundError(
            "project_to_markdown.py not found in tests/ or repo root, "
            "and import by name failed"
        ) from e


def run_script(tmp_path: Path, args: list[str]) -> Path:
    out = tmp_path / "out.md"
    full_args = ["prog"] + args + ["-o", str(out)]
    argv_backup = sys.argv[:]
    try:
        sys.argv = full_args
        main = load_module_and_get_main()
        rc = main()
        assert rc == 0
        assert out.exists()
        return out
    finally:
        sys.argv = argv_backup


def test_basic_run_generates_output(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()

    (proj / "a.py").write_text(
        '"""doc"""\nimport os\n\ndef add(a, b):\n    return a + b\n',
        encoding="utf-8",
    )
    (proj / "README.md").write_text("# Title\n\nSome text.", encoding="utf-8")
    (proj / ".hidden").write_text("secret", encoding="utf-8")

    out = run_script(tmp_path, ["-r", str(proj), "--title", "My Export"])
    txt = out.read_text(encoding="utf-8")

    assert "<!-- GENERATED" in txt
    assert "# My Export" in txt
    assert "## Overview" in txt
    assert "## Table of contents" in txt
    assert "## Files" in txt
    assert "`.hidden`" in txt
    assert "```python" in txt
    assert "`a.py`" in txt
    assert "def add(" in txt


def test_exclude_hidden_and_only_ext(tmp_path: Path):
    proj = tmp_path / "proj2"
    proj.mkdir()
    (proj / ".secret.txt").write_text("x", encoding="utf-8")
    (proj / "keep.txt").write_text("keep", encoding="utf-8")
    (proj / "skip.py").write_text("print('x')", encoding="utf-8")

    out = run_script(
        tmp_path,
        ["-r", str(proj), "--exclude-hidden", "--only-ext", ".txt"],
    )
    txt = out.read_text(encoding="utf-8")
    assert "`.secret.txt`" not in txt
    assert "`keep.txt`" in txt
    assert "`skip.py`" not in txt


def test_truncation_marker(tmp_path: Path):
    proj = tmp_path / "proj3"
    proj.mkdir()
    (proj / "big.txt").write_text("A" * 10_000, encoding="utf-8")

    out = run_script(tmp_path, ["-r", str(proj), "--max-bytes-per-file", "100"])
    txt = out.read_text(encoding="utf-8")
    assert "[TRUNCATED due to max-bytes-per-file]" in txt


def test_md_policy_render_demotes_headings(tmp_path: Path):
    proj = tmp_path / "proj4"
    proj.mkdir()
    (proj / "doc.md").write_text("# H1\n\n## H2\n", encoding="utf-8")

    out = run_script(tmp_path, ["-r", str(proj), "--md-policy", "render"])
    txt = out.read_text(encoding="utf-8")
    assert "#### H1" in txt
    assert "#### Content (rendered, headings demoted)" in txt


def test_mermaid_import_graph(tmp_path: Path):
    proj = tmp_path / "proj5"
    proj.mkdir()
    (proj / "m1.py").write_text("import json\n", encoding="utf-8")
    (proj / "m2.py").write_text("from os import path\n", encoding="utf-8")

    out = run_script(tmp_path, ["-r", str(proj), "--mermaid-import-graph"])
    txt = out.read_text(encoding="utf-8")
    assert "```mermaid" in txt
    assert "graph LR" in txt
    assert "json" in txt or "os" in txt