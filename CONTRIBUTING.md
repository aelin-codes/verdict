# Contributing to Verdict

Thanks for taking the time to contribute! 🎉

This document covers everything you need to get a working development environment and submit a pull request.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Running the Tests](#running-the-tests)
- [Linting & Formatting](#linting--formatting)
- [Project Structure](#project-structure)
- [Submitting a PR](#submitting-a-pr)
- [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct

Be respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

---

## Getting Started

### Prerequisites

- Python ≥ 3.11
- `git` on your `PATH` (Verdict shells out to `git diff`)

### Fork & clone

```bash
git clone https://github.com/verdict-dev/verdict.git
cd verdict
```

### Create a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### Install with all extras

```bash
pip install -e '.[all]'
```

This installs the package in editable mode plus `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, and `ruff`.

---

## Development Workflow

```bash
# Start the HTTP server with hot-reload
verdict serve --reload

# Start the MCP server (reads JSON-RPC 2.0 from stdin)
verdict mcp

# Run a one-off check against the current repo
verdict check --repo . --claim "your claim here"
```

---

## Running the Tests

```bash
pytest
```

Tests live in `tests/` and are split by module:

| File | Covers |
|---|---|
| `test_models.py` | Pydantic data models |
| `test_differ.py` | Git diff parser + path extraction |
| `test_ast_checker.py` | Stub detection, test-coverage flags |
| `test_analyzer.py` | End-to-end integration (uses temp git repos) |

`test_differ.py` and `test_analyzer.py` spin up real git repositories in `tmp_path` and require `git` to be available.

To run a specific file:

```bash
pytest tests/test_analyzer.py -v
```

---

## Linting & Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and import sorting.

```bash
# Check
ruff check verdict/ tests/

# Auto-fix safe issues
ruff check --fix verdict/ tests/
```

CI will fail if `ruff` reports any errors.

---

## Project Structure

```
verdict/
├── core/
│   ├── models.py       Pydantic data models
│   ├── differ.py       git diff parser
│   ├── ast_checker.py  AST static analysis
│   ├── tracer.py       sys.settrace live coverage
│   └── analyzer.py     main pipeline (orchestrator)
├── api/
│   ├── app.py          FastAPI application factory
│   └── routes.py       REST endpoints
├── mcp/
│   └── server.py       MCP server (JSON-RPC 2.0 over stdio)
└── cli.py              Click CLI
```

---

## Submitting a PR

1. **Branch** off `main`: `git checkout -b feat/my-feature`
2. **Write tests** for your change.
3. Ensure `pytest` passes and `ruff check` is clean.
4. Open a pull request against `main` and fill in the template.

For large changes, open an issue first to discuss the approach.

---

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) on GitHub Issues. Please include:

- Verdict version (`verdict --version`)
- Python version
- OS
- Minimal reproduction steps
