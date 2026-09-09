# Verdict

> **Lie detector for coding agents.**

Verdict scans the git diff after any agent claims completion, runs static and dynamic checks (AST parsing + live trace via `sys.settrace`), and returns **PASS** / **SUSPICIOUS** / **LIED** with exact `file:line` citations.

---

## Quick start

```bash
pip install 'verdict[api]'

# Run a check
verdict check --repo /path/to/repo --claim "Refactored the auth module"

# Start the HTTP API
verdict serve

# Start the MCP server (stdio)
verdict mcp
```

---

## Project structure

```
verdict-backend/
├── verdict/
│   ├── core/
│   │   ├── models.py        # VerdictResult, Citation, FileDiff
│   │   ├── differ.py        # git diff parser
│   │   ├── ast_checker.py   # AST static analysis
│   │   ├── tracer.py        # sys.settrace live coverage
│   │   └── analyzer.py      # main pipeline (orchestrator)
│   ├── api/
│   │   ├── app.py           # FastAPI application factory
│   │   └── routes.py        # REST endpoints
│   ├── mcp/
│   │   └── server.py        # MCP server (JSON-RPC 2.0 over stdio)
│   └── cli.py               # Click CLI (check / diff / serve / mcp)
├── tests/
│   ├── test_models.py
│   ├── test_differ.py
│   ├── test_ast_checker.py
│   └── test_analyzer.py
├── action.yml               # GitHub Action
├── Dockerfile               # Multi-stage container image
├── pyproject.toml
└── requirements.txt
```

---

## CLI reference

### `verdict check`

```
verdict check [OPTIONS]

Options:
  -r, --repo TEXT      Path to the git repository  [default: .]
  -c, --claim TEXT     The agent's completion claim  [required]
  --base TEXT          Base git ref to diff against  [default: HEAD]
  --compare TEXT       Optional second ref (e.g. origin/main)
  --run-tests          Run tests under sys.settrace
  --json               Output raw JSON (machine-readable)
  --no-color           Disable ANSI colour output
```

Exit code: `0` on PASS, `1` on SUSPICIOUS or LIED.

### `verdict serve`

```
verdict serve --host 0.0.0.0 --port 8000 --reload
```

Starts the FastAPI HTTP server. Interactive docs at `http://localhost:8000/docs`.

### `verdict mcp`

```
verdict mcp
```

Starts the MCP server on **stdio** (standard MCP transport). Connect any MCP-compatible agent host to it.

---

## REST API

### `GET /api/v1/health`

```json
{ "status": "ok", "version": "0.1.0" }
```

### `POST /api/v1/check`

**Request body**

```json
{
  "repo_path": "/home/user/my-app",
  "claim": "Refactored the auth module and added session expiry.",
  "base_ref": "HEAD",
  "compare_ref": null,
  "run_tests": false
}
```

**Response**

```json
{
  "verdict": "LIED",
  "claim": "Refactored the auth module and added session expiry.",
  "explanation": "1 hard discrepancy found — the agent's claim contradicts the actual diff.",
  "citations": [
    {
      "file": "src/auth/tokens.py",
      "line_start": 1,
      "line_end": null,
      "reason": "claimed-but-untouched: file mentioned in claim but not in diff"
    }
  ],
  "static_flags": [],
  "trace_flags": [],
  "diff_summary": [
    { "path": "src/auth/session.py", "added": 12, "removed": 3 }
  ]
}
```

### `GET /api/v1/verdicts`

Returns metadata about all three verdict levels.

---

## MCP tools

| Tool | Description |
|---|---|
| `verdict_check` | Full analysis — returns verdict + citations |
| `verdict_diff` | Diff summary only (files + line counts) |

---

## GitHub Action

```yaml
- name: Verify agent output
  uses: verdict-dev/action@v1
  with:
    claim: ${{ steps.agent.outputs.claim }}
    base_ref: HEAD
    compare_ref: origin/main
    fail_on: LIED   # LIED | SUSPICIOUS | never
```

Outputs: `verdict`, `explanation`, `citations` (JSON).

---

## Docker

```bash
# Build
docker build -t verdict .

# Run the API server
docker run -p 8000:8000 -v /path/to/repo:/repo verdict

# Health check
curl http://localhost:8000/api/v1/health
```

---

## Development

```bash
# Install with dev extras
pip install -e '.[all]'

# Run tests
pytest

# Lint
ruff check verdict/ tests/
```

---

## License

MIT
