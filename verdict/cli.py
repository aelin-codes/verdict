"""CLI entry point for Verdict."""
from __future__ import annotations

import json
import sys
from typing import Optional

import click

from verdict.core import analyze
from verdict.core.models import VerdictLevel


# ANSI colours
_GREEN  = "\033[1;32m"
_ORANGE = "\033[1;33m"
_RED    = "\033[1;31m"
_CYAN   = "\033[0;36m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"

def _supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or ""
    return "utf" in encoding.lower()


_USE_UNICODE = _supports_unicode()
_BULLET   = "✦" if _USE_UNICODE else "*"
_FLAG     = "⚑" if _USE_UNICODE else "[!]"
_CHECK    = "✔" if _USE_UNICODE else "[PASS]"
_CROSS    = "✘" if _USE_UNICODE else "[FAIL]"
_ERR_MARK = "✖" if _USE_UNICODE else "[ERR]"
_DASH     = "—" if _USE_UNICODE else "-"
_ARROW    = "→" if _USE_UNICODE else "->"

_LEVEL_COLOR = {
    VerdictLevel.PASS:       _GREEN,
    VerdictLevel.SUSPICIOUS: _ORANGE,
    VerdictLevel.LIED:       _RED,
    VerdictLevel.ERROR:      _RED,
}


@click.group()
@click.version_option("0.1.0", prog_name="verdict")
def cli() -> None:
    """Verdict — lie detector for coding agents."""


@cli.command("check")
@click.option("--repo", "-r", default=".", show_default=True, help="Path to the git repository.")
@click.option("--claim", "-c", required=True, help="The agent's completion claim.")
@click.option("--base", default="HEAD", show_default=True, help="Base git ref to diff against.")
@click.option("--compare", default=None, help="Optional second ref (e.g. origin/main).")
@click.option("--run-tests", is_flag=True, default=False, help="Run test suite and verify coverage.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
@click.option("--no-color", is_flag=True, default=False, help="Disable ANSI colour output.")
def check(
    repo: str,
    claim: str,
    base: str,
    compare: Optional[str],
    run_tests: bool,
    output_json: bool,
    no_color: bool,
) -> None:
    """Run a verdict check on a git repository."""
    try:
        result = analyze(
            repo_path=repo,
            claim=claim,
            base_ref=base,
            compare_ref=compare,
            run_tests=run_tests,
        )
    except (ValueError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if output_json:
        click.echo(json.dumps(result.to_dict(), indent=2))
        if result.level == VerdictLevel.ERROR:
            sys.exit(2)
        sys.exit(0 if result.level == VerdictLevel.PASS else 1)

    # ── human-readable output ───────────────────────────────────────────────
    def c(color: str, text: str) -> str:
        return f"{color}{text}{_RESET}" if not no_color else text

    cmp_str = f" ({base}{(' ' + _ARROW + ' ' + compare) if compare else ''})"
    click.echo()
    click.echo(c(_DIM, f"  {_BULLET}  Running static analysis  (AST parse)"))
    click.echo(c(_DIM, f"  {_BULLET}  Scanning git diff        {cmp_str}"))
    if run_tests:
        click.echo(c(_DIM, f"  {_BULLET}  Running test coverage    (LCOV)"))
    click.echo()

    for d in result.diff_summary:
        added   = c(_GREEN,  f"+{d.added}")
        removed = c(_RED,    f"-{d.removed}")
        click.echo(f"  {d.path:<50} {added} / {removed}")

    if result.citations:
        click.echo()
        for cit in result.citations:
            click.echo(c(_ORANGE, f"  {_FLAG} {cit}"))

    click.echo()
    level_color = _LEVEL_COLOR.get(result.level, _RED)
    if result.level == VerdictLevel.PASS:
        mark = _CHECK
    elif result.level == VerdictLevel.ERROR:
        mark = _ERR_MARK
    else:
        mark = _CROSS
    click.echo(f"  {c(level_color, mark + '  ' + result.level.value)}  {c(_DIM, _DASH + ' ' + result.explanation)}")
    click.echo()

    if result.level == VerdictLevel.ERROR:
        sys.exit(2)
    sys.exit(0 if result.level == VerdictLevel.PASS else 1)


@cli.command("diff")
@click.option("--repo", "-r", default=".", show_default=True)
@click.option("--base", default="HEAD", show_default=True)
@click.option("--compare", default=None)
@click.option("--json", "output_json", is_flag=True, default=False)
def diff_cmd(repo: str, base: str, compare: Optional[str], output_json: bool) -> None:
    """Print the git diff summary for a repository."""
    from verdict.core.differ import get_diff
    diffs = get_diff(repo, base=base, compare=compare)
    if output_json:
        click.echo(json.dumps([{"path": d.path, "added": d.added, "removed": d.removed} for d in diffs], indent=2))
        return
    for d in diffs:
        click.echo(f"{d.path}  +{d.added} / -{d.removed}")


@cli.command("serve")
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, default=False)
def serve(host: str, port: int, reload: bool) -> None:
    """Start the HTTP API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("uvicorn is required: pip install 'verdict[api]'", err=True)
        sys.exit(1)
    uvicorn.run("verdict.api.app:app", host=host, port=port, reload=reload)


@cli.command("mcp")
@click.option("--port", default=None, type=int, help="Ignored — MCP uses stdio.")
def mcp_cmd(port: Optional[int]) -> None:
    """Start the MCP server on stdio."""
    from verdict.mcp import run_mcp_server
    run_mcp_server(port=port)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
