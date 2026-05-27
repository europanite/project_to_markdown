# [Project to Markdown](https://github.com/europanite/project_to_markdown "Project to Markdown")

[![Python](https://img.shields.io/badge/python-3.9|%203.10%20|%203.11|%203.12|%203.13-blue)](https://www.python.org/)
![OS](https://img.shields.io/badge/OS-Linux%20%7C%20macOS%20%7C%20Windows-blue)

[![CI](https://github.com/europanite/project_to_markdown/actions/workflows/ci.yml/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/ci.yml)
[![Python Lint](https://github.com/europanite/project_to_markdown/actions/workflows/lint.yml/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/lint.yml)
[![pages-build-deployment](https://github.com/europanite/project_to_markdown/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/pages/pages-build-deployment)
[![CodeQL Advanced](https://github.com/europanite/project_to_markdown/actions/workflows/codeql.yml/badge.svg)](https://github.com/europanite/project_to_markdown/actions/workflows/codeql.yml)

Project Documentation.

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


## Project ignore files

By default, `make_md.py` reads these files from the directory passed to `--root`:

- `.gitignore`
- `.dockerignore`

Patterns imported from those files are merged into the built-in ignore list before `os.walk()` starts. This means ignored directories can be pruned before traversal.

Supported project-ignore behavior:

- Blank lines are ignored.
- Lines beginning with `#` are treated as comments.
- Escaped leading `\#` and `\!` are treated as literal `#` and `!` patterns.
- Directory rules ending with `/` are expanded so that their descendants are ignored.
- Leading `/` keeps a pattern anchored to the `--root` directory.
- Positive ignore patterns are imported.

Negation rules beginning with `!` are skipped. The exporter uses a positive ignore list rather than a full ordered gitignore engine, so importing negation rules directly would be unsafe.

To disable project ignore file loading:

```bash
python make_md.py --root /path/to/project --no-project-ignore-files
```

## Additional ignore patterns

Use `--ignore` to add patterns manually:

```bash
python make_md.py --root /path/to/project --ignore "**/logs/**" --ignore "*.sqlite"
```

The matcher supports standard glob matching plus a segment rule such as:

```text
**/node_modules/**
```

That form matches any path containing a `node_modules` segment.

## Useful options

```bash
python make_md.py \
  --root /path/to/project \
  --output project_export.md \
  --max-bytes-per-file 300000 \
  --md-policy fence \
  --mermaid-import-graph
```

Common options:

- `--root`: target project directory. Required.
- `--output`: output Markdown path.
- `--ignore`: extra ignore pattern. Can be repeated.
- `--no-project-ignore-files`: do not load `<root>/.gitignore` or `<root>/.dockerignore`.
- `--exclude-hidden`: exclude dotfiles and dot-directories.
- `--max-bytes-per-file`: maximum bytes included per file.
- `--only-ext`: include only files with a specific extension. Can be repeated.
- `--md-policy fence|render|skip`: controls how Markdown files are included.
- `--mermaid-import-graph`: emits a simple Mermaid graph for Python imports.
- `--no-metrics`: disables metrics in the output.
- `--no-summaries`: disables auto summaries.

## Example

```bash
python make_md.py \
  --root . \
  --output latest_project_export.md \
  --ignore "*.log" \
  --ignore "**/tmp/**"
```

This command exports the current directory, applies the built-in ignore rules, imports `.gitignore` and `.dockerignore` from the current directory, adds two extra ignore patterns, and writes `latest_project_export.md`.

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

### Test

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.test.txt
pytest
```

### Deactivate environment

```bash
deactivate
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


