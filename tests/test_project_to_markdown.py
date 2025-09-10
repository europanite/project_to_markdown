import sys
from pathlib import Path

import importlib
import types


def run_script(tmp_path: Path, args: list[str]) -> Path:
    out = tmp_path / "out.md"
    full_args = ["prog"] + args + ["-o", str(out)]
    old_argv = sys.argv[:]
    try:
        sys.argv = full_args
        mod = importlib.import_module("project_to_markdown")
        mod = importlib.reload(mod)
        rc = mod.main()
        assert rc == 0
        assert out.exists()
        return out
    finally:
        sys.argv = old_argv


def test_basic_run_generates_output(tmp_path: Path, monkeypatch):
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
        [
            "-r",
            str(proj),
            "--exclude-hidden",   
            "--only-ext",
            ".txt",               
        ],
    )
    txt = out.read_text(encoding="utf-8")
    assert "`.secret.txt`" not in txt
    assert "`keep.txt`" in txt
    assert "`skip.py`" not in txt


def test_truncation_marker(tmp_path: Path):
    proj = tmp_path / "proj3"
    proj.mkdir()
    big = proj / "big.txt"
    big.write_text("A" * 10_000, encoding="utf-8")

    out = run_script(
        tmp_path,
        ["-r", str(proj), "--max-bytes-per-file", "100"],  
    )
    txt = out.read_text(encoding="utf-8")
    assert "[TRUNCATED due to max-bytes-per-file]" in txt


def test_md_policy_render_demotes_headings(tmp_path: Path):
    proj = tmp_path / "proj4"
    proj.mkdir()
    (proj / "doc.md").write_text("# H1\n\n## H2\n", encoding="utf-8")

    out = run_script(
        tmp_path,
        ["-r", str(proj), "--md-policy", "render"],
    )
    txt = out.read_text(encoding="utf-8")
    assert "#### H1" in txt
    assert "#### Content (rendered, headings demoted)" in txt


def test_mermaid_import_graph(tmp_path: Path):
    proj = tmp_path / "proj5"
    proj.mkdir()
    (proj / "m1.py").write_text("import json\n", encoding="utf-8")
    (proj / "m2.py").write_text("from os import path\n", encoding="utf-8")

    out = run_script(
        tmp_path,
        ["-r", str(proj), "--mermaid-import-graph"],
    )
    txt = out.read_text(encoding="utf-8")
    assert "```mermaid" in txt
    assert "graph LR" in txt
    assert "json" in txt or "os" in txt
