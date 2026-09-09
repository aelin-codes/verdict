# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — 2026-09-09

### Added

- **Core analysis engine** (`verdict/core/analyzer.py`) — orchestrates diff parsing, AST analysis, and live tracing into a single `analyze()` call returning `PASS`, `SUSPICIOUS`, or `LIED`.
- **Git differ** (`verdict/core/differ.py`) — parses unified `git diff` output into structured `FileDiff` objects; extracts file paths mentioned in natural-language claims.
- **AST checker** (`verdict/core/ast_checker.py`) — walks the Python AST of changed files to detect stub implementations, missing test coverage, and symbol discrepancies.
- **Live tracer** (`verdict/core/tracer.py`) — injects a `sys.settrace`-based shim into the subprocess test runner and records every executed line; cross-references against the claimed diff.
- **Data models** (`verdict/core/models.py`) — Pydantic models for `VerdictResult`, `Citation`, `FileDiff`, and the `VerdictLevel` enum.
- **CLI** (`verdict/cli.py`) — Click-based command group with four sub-commands: `check`, `diff`, `serve`, `mcp`.
- **REST API** (`verdict/api/`) — FastAPI application with `/api/v1/health`, `/api/v1/check`, and `/api/v1/verdicts` endpoints; full OpenAPI docs at `/docs`.
- **MCP server** (`verdict/mcp/server.py`) — JSON-RPC 2.0 server over stdio exposing `verdict_check` and `verdict_diff` tools to any MCP-compatible agent host.
- **GitHub Action** (`action.yml`) — composite action that installs Verdict and runs `verdict check`, writing outputs (`verdict`, `explanation`, `citations`) to `$GITHUB_OUTPUT` and the job summary.
- **Dockerfile** — multi-stage image; builder produces a wheel, runtime image adds `git` and runs the API server as a non-root user.
- **Test suite** — 4 modules covering models, differ, AST checker, and end-to-end analysis (integration tests using temporary git repos).

[Unreleased]: https://github.com/verdict-dev/verdict/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/verdict-dev/verdict/releases/tag/v0.1.0
