"""MCP server — exposes Verdict as a tool to any MCP-compatible agent host."""
from __future__ import annotations

import json
import sys
from typing import Any

from verdict.core import analyze

# MCP wire protocol helpers (JSON-RPC 2.0 over stdio)


def _send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


# ── Tool definitions ───────────────────────────────────────────────────

TOOLS = [
    {
        "name": "verdict_check",
        "description": (
            "Verify an agent's completion claim against the actual git diff. "
            "Returns PASS, SUSPICIOUS, or LIED with file:line citations."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["repo_path", "claim"],
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the git repository.",
                },
                "claim": {
                    "type": "string",
                    "description": "The agent's natural-language completion statement.",
                },
                "base_ref": {
                    "type": "string",
                    "default": "HEAD",
                    "description": "Git ref to diff against.",
                },
                "compare_ref": {
                    "type": "string",
                    "description": "Optional second ref (e.g. 'origin/main').",
                },
                "run_tests": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run the test suite under sys.settrace.",
                },
            },
        },
    },
    {
        "name": "verdict_diff",
        "description": "Return the git diff summary (added/removed lines per file) for a repository.",
        "inputSchema": {
            "type": "object",
            "required": ["repo_path"],
            "properties": {
                "repo_path": {"type": "string"},
                "base_ref": {"type": "string", "default": "HEAD"},
                "compare_ref": {"type": "string"},
            },
        },
    },
]


# ── Handlers ─────────────────────────────────────────────────────────────

def _handle_verdict_check(args: dict) -> dict:
    result = analyze(
        repo_path=args["repo_path"],
        claim=args["claim"],
        base_ref=args.get("base_ref", "HEAD"),
        compare_ref=args.get("compare_ref"),
        run_tests=args.get("run_tests", False),
    )
    return result.to_dict()


def _handle_verdict_diff(args: dict) -> dict:
    from verdict.core.differ import get_diff
    diffs = get_diff(
        repo_path=args["repo_path"],
        base=args.get("base_ref", "HEAD"),
        compare=args.get("compare_ref"),
    )
    return {"files": [{"path": d.path, "added": d.added, "removed": d.removed} for d in diffs]}


_TOOL_MAP = {
    "verdict_check": _handle_verdict_check,
    "verdict_diff": _handle_verdict_diff,
}


# ── Server loop ───────────────────────────────────────────────────────────

def run_mcp_server(port: int | None = None) -> None:  # noqa: ARG001
    """
    Start the MCP server on stdio (the MCP standard transport).
    ``port`` is accepted for CLI compatibility but ignored — MCP uses stdio.
    """
    while True:
        msg = _recv()
        if msg is None:
            break

        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "verdict", "version": "0.1.0"},
                },
            })

        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            handler = _TOOL_MAP.get(tool_name)
            if handler is None:
                _send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                })
            else:
                try:
                    output = handler(tool_args)
                    _send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(output, indent=2)}],
                            "isError": False,
                        },
                    })
                except Exception as exc:  # noqa: BLE001
                    _send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": str(exc)}],
                            "isError": True,
                        },
                    })

        elif method == "notifications/initialized":
            pass  # no response needed

        else:
            if req_id is not None:
                _send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                })
