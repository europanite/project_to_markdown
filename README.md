# [Project to Markdown](https://github.com/europanite/project_to_markdown "Project to Markdown")

[![CI (Python)](https://github.com/europanite/project_to_markdown/actions/workflows/ci.yml/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/ci.yml)
[![Python Lint](https://github.com/europanite/project_to_markdown/actions/workflows/lint.yml/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/lint.yml)
[![pages-build-deployment](https://github.com/europanite/project_to_markdown/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/pages/pages-build-deployment)

Export an entire multi-file project into **one Markdown file** that’s easy for long-context LLMs (e.g., ChatGPT) to read and reason about.

- Makes code review, refactoring, and architecture discussions frictionless
- Preserves **file boundaries** with fenced blocks (even for `.md` files)
- Adds **overview metrics**, a **project tree**, and a **TOC** for quick navigation

---

## Features

- **Safe Markdown for LLMs**  
  Every file is wrapped in code fences (or rendered/demoted, if you prefer) so your report’s headings don’t collide with project docs.
- **Overview & metrics**  
  - Totals (files, bytes, LOC/SLOC, TODOs)  
  - Language mix, largest/longest files  
  - Best-effort dependency sniffing (`requirements.txt`, `pyproject.toml`, `package.json`)
- **Per-file details**  
  - Size, LOC/SLOC, TODO count, mtime, SHA1 digest  
  - Python: function/class counts & a simple complexity estimate
- **Table of Contents & Project Tree**  
  Anchors per file, plus a compact tree of included paths.
- **Optional Mermaid** Python import graph (`--mermaid-import-graph`)
- **Large-file truncation with markers**  
  Clear `[TRUNCATED]` markers when a file exceeds `--max-bytes-per-file`.

---

## Requirements

- **Python 3.8+**
- No third-party dependencies (standard library only)

---

## Installation

Just copy the script somewhere on your `PATH`:

```bash
# Download the script into your project.
curl -O https://raw.githubusercontent.com/europanite/project_to_markdown/main/make_md.py
# Analize the project.
python make_md.py -r .
```
---

## Usage

Basic:

```bash
python make_md.py -r /path/to/project
# => ./<project>_YYYYMMDD_HHMMSS.md
```

Exclude hidden files:

```bash
python make_md.py -r . --exclude-hidden
```

Only specific extensions:

```bash
python make_md.py -r .   --only-ext .py --only-ext .md --only-ext .yml --only-ext .toml --only-ext .json
```

Render project Markdown instead of fencing:

```bash
python make_md.py -r . --md-policy render
```

Add a Python import graph (Mermaid):

```bash
python make_md.py -r . --mermaid-import-graph
```

Custom title & output:

```bash
python make_md.py -r . --title "MyApp Export" -o myapp_dump.md
```

---

## Options

```text
-r, --root <dir>             Project root directory (required)
-o, --output <file>          Output Markdown file (default: <project>_<timestamp>.md)
--ignore <pattern>           Ignore patterns (fnmatch; supports **). Repeatable.
--exclude-hidden             Exclude hidden files/dirs (dot-prefixed). Default is include.
--max-bytes-per-file <n>     Max bytes per file to include (default: 300000)
--only-ext <.ext>            Whitelist extensions; repeat to add more (e.g., .py .md ...)
--title <str>                Top-level title in the generated Markdown
--md-policy {fence,render,skip}
                             How to include project .md files:
                               - fence  : wrap in ```markdown (default)
                               - render : demote headings and render inline
                               - skip   : omit them
--top-n-largest <N>          Show N largest/longest files (default: 12)
--mermaid-import-graph       Include a naive Mermaid graph of Python imports
--no-metrics                 Disable project/file metrics
--no-summaries               Disable auto summaries
```

---


## Tips for ChatGPT / LLM workflows

- Paste the generated Markdown into a long-context model.  
- Use the **TOC** and file anchors to reference exact files.  
- If a file shows `[TRUNCATED]`, consider attaching that file separately for deep dives.  
- Prefer `--md-policy fence` (default) so the report’s headings aren’t confused with project docs.

---

## Limitations

- Binary files are skipped (heuristic: NUL bytes / decoding failures).  
- Dependency detection is best-effort (no lockfile resolution).  
- The Python import graph is naive (text-level, not AST-based module resolution).

---

## License

- Apache License 2.0
