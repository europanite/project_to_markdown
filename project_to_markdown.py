#!/usr/bin/env python3
"""
project_to_markdown.py

Dump an entire project into one Markdown file optimized for
long-context LLM discussion (e.g., ChatGPT).

What's new in this build:
- Hidden files are INCLUDED by default.
- New option `--exclude-hidden` to omit dotfiles/directories when desired.
- Everything else: fenced content (including .md), overview, metrics, TOC,
  (optional) Python import graph, truncation markers, dynamic default output
  filename (<project>_YYYYMMDD_HHMMSS.md).

Usage (typical):
    python project_to_markdown.py -r /path/to/project
    python project_to_markdown.py -r . --exclude-hidden
    python project_to_markdown.py -r . --mermaid-import-graph --no-summaries
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

DEFAULT_IGNORES = [
    ".git/**",
    ".hg/**",
    ".svn/**",
    "__pycache__/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    ".venv/**",
    "venv/**",
    ".DS_Store",
]

# File extension -> code fence language
EXT_TO_LANG = {
    ".py": "python",
    ".ipynb": "json",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sh": "bash",
    ".zsh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".m": "objectivec",
    ".mm": "objectivec",
    ".cs": "csharp",
    ".sql": "sql",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".vue": "vue",
    ".svelte": "svelte",
    ".xml": "xml",
    ".gradle": "groovy",
    ".groovy": "groovy",
    ".dockerfile": "dockerfile",
    "Dockerfile": "dockerfile",
    ".dockerignore": "",
    ".env": "",
    ".txt": "",
    "": "",
}

# Comment prefixes to estimate SLOC and brief descriptions
COMMENT_PREFIXES = {
    "python": "#",
    "bash": "#",
    "ruby": "#",
    "ini": ";",
    "json": "",
    "yaml": "#",
    "toml": "#",
    "javascript": "//",
    "typescript": "//",
    "tsx": "//",
    "jsx": "//",
    "java": "//",
    "c": "//",
    "cpp": "//",
    "csharp": "//",
    "go": "//",
    "rust": "//",
    "php": "//",
    "swift": "//",
    "kotlin": "//",
    "objectivec": "//",
    "sql": "--",
    "html": "",
    "css": "",
    "markdown": "",
    "xml": "",
    "dockerfile": "#",
    "groovy": "//",
}

# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(
        description=("Extract project files into one Markdown for LLM discussion.")
    )
    p.add_argument("-r", "--root", required=True, help="Project root directory")
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output markdown file (default: <project>_<timestamp>.md)",
    )
    p.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore patterns (fnmatch, supports **)",
    )
    # Hidden files are included by default. Use --exclude-hidden to turn them off.
    p.add_argument(
        "--exclude-hidden",
        action="store_true",
        help="Exclude hidden files/dirs (those starting with a dot)",
    )
    p.add_argument(
        "--max-bytes-per-file",
        type=int,
        default=300_000,
        help="Max bytes per file to include",
    )
    p.add_argument(
        "--only-ext",
        action="append",
        default=[],
        help="Whitelist extensions (repeatable)",
    )
    p.add_argument("--title", default=None, help="Top-level title in markdown")
    p.add_argument(
        "--md-policy",
        choices=["fence", "render", "skip"],
        default="fence",
        help=(
            "How to include project .md files: fence as code, render (demote " "headings), or skip"
        ),
    )
    p.add_argument(
        "--top-n-largest",
        type=int,
        default=12,
        help="Show top-N largest/longest files",
    )
    p.add_argument(
        "--mermaid-import-graph",
        action="store_true",
        help="Emit Mermaid graph for Python imports",
    )
    p.add_argument("--no-metrics", dest="with_metrics", action="store_false")
    p.add_argument("--no-summaries", dest="with_summaries", action="store_false")
    p.set_defaults(with_metrics=True, with_summaries=True)

    args = p.parse_args()

    if args.output is None:
        root = Path(args.root).resolve()
        proj = root.name
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"{proj}_{ts}.md"

    return args


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def norm_patterns(patterns):
    return [pat.strip() for pat in patterns if pat.strip()]


def is_hidden(path):
    # Treat anything with a dot-leading segment as hidden (except . and ..)
    return any(part.startswith(".") and part not in (".", "..") for part in path.parts)


def matches_ignore(rel_path, patterns):
    s = str(rel_path).replace(os.sep, "/")
    return any(fnmatch.fnmatch(s, pat) for pat in patterns)


def detect_language(path):
    if path.name == "Dockerfile":
        return "dockerfile"
    return EXT_TO_LANG.get(path.suffix, "")


def is_probably_binary(sample):
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def read_text_safely(p, max_bytes):
    data = p.read_bytes()
    nbytes = len(data)
    truncated = False
    if nbytes > max_bytes:
        data = data[:max_bytes]
        truncated = True
    if is_probably_binary(data[:4096]):
        return ("", False, nbytes)
    text = data.decode("utf-8", errors="replace")
    return (text, truncated, nbytes)


def sha1_of_text(s):
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def sloc_of_text(text, lang):
    """Very rough SLOC: non-empty lines not starting with single-line comment."""
    com = COMMENT_PREFIXES.get(lang or "", None)
    cnt = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if com and stripped.startswith(com):
            continue
        cnt += 1
    return cnt


def count_todos(text):
    return len(re.findall(r"\bTODO\b|FIXME|XXX", text, flags=re.IGNORECASE))


def extract_brief_description(text, lang, max_lines=5):
    """
    Try to extract a short description from leading comments or docstring.
    """
    t = text.lstrip()
    if lang == "python":
        if t.startswith(('"""', "'''")):
            quote = t[:3]
            end = t.find(quote, 3)
            if end != -1:
                doc = t[3:end]
                return "\n".join(doc.strip().splitlines()[:max_lines])
    prefix = COMMENT_PREFIXES.get(lang, "")
    if prefix:
        lines = []
        for line in text.splitlines():
            if line.strip().startswith(prefix):
                cleaned = line.strip()[len(prefix) :].lstrip()
                lines.append(cleaned)
                if len(lines) >= max_lines:
                    break
            elif line.strip() == "":
                if lines:
                    lines.append("")
            else:
                break
        out = "\n".join(lines).strip()
        if out:
            return out
    return "\n".join(text.splitlines()[:2]).strip()


def auto_summary(text, lang, max_len=200):
    """
    Deterministic one-liner summaries (no AI):
      - markdown: first heading line
      - python: first docstring line OR counts of defs/classes
      - others: first non-empty line
    """
    if not text:
        return ""
    if lang == "markdown":
        for line in text.splitlines():
            m = re.match(r"\s*#+\s+(.*)", line)
            if m:
                return m.group(1).strip()[:max_len]
    if lang == "python":
        t = text.lstrip()
        if t.startswith(('"""', "'''")):
            quote = t[:3]
            end = t.find(quote, 3)
            if end != -1:
                first = t[3:end].strip().splitlines()[:1]
                if first:
                    return first[0][:max_len]
        funcs = len(re.findall(r"^\s*def\s+\w+\(", text, flags=re.MULTILINE))
        classes = len(re.findall(r"^\s*class\s+\w+\(", text, flags=re.MULTILINE))
        return (f"Python module with {funcs} functions and {classes} classes.")[:max_len]
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:max_len]
    return ""


def demote_markdown_headings(text, levels=3):
    if levels <= 0:
        return text
    out_lines = []
    for line in text.splitlines():
        m = re.match(r"(\s*)(#+)\s*(.*)$", line)
        if m:
            lead, hashes, rest = m.groups()
            out_lines.append(f"{lead}{'#' * (len(hashes) + levels)} {rest}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def build_tree(root, files):
    """Pretty-prints a tree that reflects only the included files."""
    rel_files = [f.relative_to(root) for f in files]
    dirs = set()
    for f in rel_files:
        parent = f.parent
        while parent != Path("."):
            dirs.add(parent)
            parent = parent.parent
    entries = sorted(dirs) + sorted(rel_files)
    lines = [str(root.name) + "/"]
    for path in entries:
        parts = list(path.parts)
        indent = "  " * (len(parts) - 1)
        branch = "├─ " if (root / path).is_dir() else "└─ "
        name = parts[-1] + ("/" if (root / path).is_dir() else "")
        lines.append(indent + branch + name)
    return "```\n" + "\n".join(lines) + "\n```"


def slugify(path_like):
    s = re.sub(r"[^A-Za-z0-9/_\-.]+", "-", path_like)
    s = s.strip("-").replace("/", "-")
    return s or "file"


def detect_dependencies(root):
    """Best-effort dependency sniffing (no lock/resolution)."""
    deps = {}
    # requirements.txt
    req = root / "requirements.txt"
    if req.exists():
        try:
            pkgs = []
            for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkgs.append(line)
            if pkgs:
                deps["python_requirements"] = pkgs
        except Exception:
            pass
    # pyproject.toml (naive preview)
    pyp = root / "pyproject.toml"
    if pyp.exists():
        try:
            txt = pyp.read_text(encoding="utf-8", errors="ignore")
            m = re.findall(r'(?m)^\s*([A-Za-z0-9_.-]+)\s*=\s*["\']?([^"\']+)["\']?', txt)
            if m:
                deps["pyproject_toml_preview"] = [f"{k}={v}" for k, v in m][:50]
        except Exception:
            pass
    # package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            obj = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            for k in ("dependencies", "devDependencies", "peerDependencies"):
                if k in obj and isinstance(obj[k], dict) and obj[k]:
                    deps[f"npm_{k}"] = [f"{n}@{v}" for n, v in obj[k].items()]
        except Exception:
            pass
    return deps


def python_imports(text):
    """Very naive import parser used only for a best-effort graph."""
    mods = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"from\s+([a-zA-Z0-9_\.]+)\s+import\s+", line)
        if m:
            mods.add(m.group(1).split(".")[0])
            continue
        m = re.match(r"import\s+([a-zA-Z0-9_\.]+)", line)
        if m:
            first = m.group(1).split(",")[0].strip()
            mods.add(first.split(".")[0])
    return mods


def simple_cyclomatic_complexity_py(text):
    """Super-naive cyclomatic complexity: 1 + count of branching keywords."""
    keywords = r"\b(if|elif|for|while|and|or|try|except|with|case)\b"
    return 1 + len(re.findall(keywords, text))


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] Root not found or not a directory: {root}", file=sys.stderr)
        return 2

    ignore_patterns = norm_patterns(DEFAULT_IGNORES + args.ignore)

    # Walk the tree; by default we INCLUDE hidden entries. If --exclude-hidden is
    # set, we drop hidden dirs and files (unless they pass explicit ignore/only-ext
    # logic separately).
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        rel_dir = dp.relative_to(root)

        def keep_dir(dname):
            if matches_ignore(rel_dir / dname, ignore_patterns):
                return False
            if args.exclude_hidden and dname.startswith("."):
                return False
            return True

        # mutate dirnames in-place so os.walk prunes hidden dirs when requested
        dirnames[:] = [d for d in dirnames if keep_dir(d)]

        for fn in filenames:
            p = dp / fn
            rel = p.relative_to(root)
            if matches_ignore(rel, ignore_patterns):
                continue
            if args.exclude_hidden and is_hidden(rel):
                continue
            if p.is_dir():
                continue
            if args.only_ext and p.suffix not in args.only_ext and p.name != "Dockerfile":
                continue
            files.append(p)

    # Collect per-file info
    total_bytes = 0
    lang_counter = Counter()
    file_records = []
    py_import_graph = defaultdict(set)

    for p in files:
        lang = detect_language(p)
        text, truncated, nbytes = read_text_safely(p, args.max_bytes_per_file)
        total_bytes += nbytes
        lang_counter[lang or "plain"] += 1

        loc = len(text.splitlines()) if text else 0
        sloc = sloc_of_text(text, lang) if text else 0
        todos = count_todos(text) if text else 0
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        digest = sha1_of_text(text) if text else ""

        py_funcs = py_classes = py_complex = 0
        if lang == "python" and text:
            try:
                tree = ast.parse(text)
                py_funcs = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
                py_classes = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            except Exception:
                pass
            py_complex = simple_cyclomatic_complexity_py(text)

        rec = {
            "path": p.relative_to(root),
            "lang": lang,
            "text": text,
            "truncated": truncated,
            "nbytes": nbytes,
            "loc": loc,
            "sloc": sloc,
            "todos": todos,
            "mtime": mtime,
            "sha1": digest,
            "py_funcs": py_funcs,
            "py_classes": py_classes,
            "py_complex": py_complex,
        }
        file_records.append(rec)

        if lang == "python" and text:
            imports = python_imports(text)
            if imports:
                py_import_graph[str(p.relative_to(root))].update(imports)

    file_records.sort(key=lambda r: str(r["path"]).lower())

    # Overview pieces
    deps = detect_dependencies(root)
    largest = sorted(file_records, key=lambda r: r["nbytes"], reverse=True)[: args.top_n_largest]
    longest = sorted(file_records, key=lambda r: r["loc"], reverse=True)[: args.top_n_largest]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_loc = sum(r["loc"] for r in file_records)
    total_sloc = sum(r["sloc"] for r in file_records)
    total_todos = sum(r["todos"] for r in file_records)

    # Compose Markdown
    lines = []
    title = args.title or f"Project Export: {root.name}"
    lines.append(f"<!-- GENERATED at {now} -->")
    lines.append(f"# {title}\n")

    # Overview
    lines.append("## Overview\n")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Files: **{len(file_records)}**")
    lines.append(f"- Total size: **{total_bytes} bytes**")
    if args.with_metrics:
        lines.append(f"- Total LOC: {total_loc} | SLOC: {total_sloc} | TODOs: {total_todos}")
    lines.append("")

    # Language mix
    if lang_counter:
        lines.append("### Language mix")
        for lang, count in lang_counter.most_common():
            lines.append(f"- {lang or '(plain)'}: {count}")
        lines.append("")

    # Dependencies
    if deps:
        lines.append("### Detected dependencies (best-effort)")
        for k, arr in deps.items():
            lines.append(f"- **{k}** ({len(arr)}):")
            for x in arr[:50]:
                lines.append(f"  - {x}")
            if len(arr) > 50:
                lines.append("  - ...")
        lines.append("")

    # Largest / Longest
    if largest:
        lines.append(f"### Top {len(largest)} largest files (bytes)")
        for r in largest:
            lines.append(f"- `{r['path']}` — {r['nbytes']} bytes")
        lines.append("")
    if longest:
        lines.append(f"### Top {len(longest)} longest files (LOC)")
        for r in longest:
            lines.append(f"- `{r['path']}` — {r['loc']} LOC")
        lines.append("")

    # Project tree
    lines.append("### Project tree (included subset)")
    lines.append(build_tree(root, [root / r["path"] for r in file_records]))
    lines.append("")

    # TOC
    lines.append("## Table of contents (files)\n")
    for idx, r in enumerate(file_records, start=1):
        anchor = slugify(str(r["path"]))
        lines.append(f"- {idx}. [{r['path']}](#{anchor})")
    lines.append("")

    # Python import graph (optional)
    if args.mermaid_import_graph and py_import_graph:
        lines.append("## Python import graph (naive)\n")
        lines.append("```mermaid")
        lines.append("graph LR")
        for file_path, imports in py_import_graph.items():
            file_node = slugify(file_path)
            for mod in sorted(imports):
                mod_node = slugify(f"mod-{mod}")
                lines.append(f'  {file_node}["{file_path}"] --> {mod_node}["{mod}"]')
        lines.append("```")
        lines.append("")

    # Files
    lines.append("---\n")
    lines.append("## Files\n")
    for i, r in enumerate(file_records, start=1):
        rel = str(r["path"])
        anchor = slugify(rel)
        lang = r["lang"]
        text = r["text"]
        truncated = r["truncated"]
        nbytes = r["nbytes"]

        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"### {i}. `{rel}`")
        # Per-file metrics
        if args.with_metrics:
            meta = [
                f"Size: {nbytes} bytes",
                f"LOC: {r['loc']}",
                f"SLOC: {r['sloc']}",
                f"TODOs: {r['todos']}",
                f"Modified: {r['mtime']}",
                f"SHA1: {str(r['sha1'])[:12]}",
            ]
            if lang == "python":
                meta.append(
                    "Py: "
                    f"funcs={r['py_funcs']} "
                    f"classes={r['py_classes']} "
                    f"complexity≈{r['py_complex']}"
                )
            lines.append("- " + " | ".join(meta))
        else:
            lines.append(f"- Size: {nbytes} bytes")

        # Brief & Auto Summary
        if text:
            brief = extract_brief_description(text, lang)
            if brief:
                lines.append("\n#### Brief")
                lines.append(brief)
            if args.with_summaries:
                s = auto_summary(text, lang)
                if s:
                    lines.append("\n#### Auto Summary")
                    lines.append(s)
            lines.append("")

        # Markdown policy handling
        if lang == "markdown":
            if args.md_policy == "skip":
                lines.append("_Skipped per --md-policy=skip_")
                lines.append("")
                continue
            elif args.md_policy == "fence":
                lines.append("#### Content (verbatim)\n")
                lines.append("```markdown")
                lines.append((text or "").rstrip())
                if truncated:
                    lines.append("\n<!-- [TRUNCATED due to max-bytes-per-file] -->")
                lines.append("```")
                lines.append("")
                continue
            elif args.md_policy == "render":
                lines.append("#### Content (rendered, headings demoted)\n")
                demoted = demote_markdown_headings(text or "", levels=3)
                lines.append(demoted.rstrip())
                if truncated:
                    lines.append("\n<!-- [TRUNCATED due to max-bytes-per-file] -->")
                lines.append("")
                continue

        # Others -> fenced code
        lines.append("#### Content\n")
        fence_lang = (lang or "").strip()
        lines.append(f"```{fence_lang}".rstrip())
        if text:
            lines.append(text.rstrip())
        if truncated:
            lines.append("\n# [TRUNCATED due to max-bytes-per-file]")
        lines.append("```")
        lines.append("")

    out_path = Path(args.output).resolve()
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    main()
