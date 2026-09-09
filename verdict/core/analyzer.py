"""Main Verdict engine — orchestrates differ, AST checker, and tracer."""
from __future__ import annotations

from pathlib import Path

from .ast_checker import (
    check_claim_against_ast,
    check_missing_test_coverage,
    detect_stub_implementations,
)
from .differ import extract_mentioned_paths, get_diff, get_staged_diff
from .models import Citation, FileDiff, VerdictLevel, VerdictResult
from .tracer import check_coverage_gaps, run_tests_with_trace


def analyze(
    repo_path: str,
    claim: str,
    base_ref: str = "HEAD",
    compare_ref: str | None = None,
    run_tests: bool = False,
    test_command: list[str] | None = None,
) -> VerdictResult:
    """
    Core analysis pipeline.

    Args:
        repo_path:    Path to the git repository.
        claim:        The agent's natural-language completion statement.
        base_ref:     Git ref to diff against (default: HEAD).
        compare_ref:  Optional second ref (e.g. "origin/main").
        run_tests:    If True, execute the test suite under sys.settrace.
        test_command: Override the default pytest command when run_tests=True.

    Returns:
        A VerdictResult with level PASS, SUSPICIOUS, or LIED.
    """
    repo = str(Path(repo_path).resolve())

    # 1. Git diff -------------------------------------------------------
    try:
        diffs: list[FileDiff] = get_diff(repo, base=base_ref, compare=compare_ref)
    except Exception as exc:  # noqa: BLE001
        diffs = []
        static_flags = [f"Could not read git diff: {exc}"]
    else:
        static_flags: list[str] = []

    changed_paths = [d.path for d in diffs]
    mentioned_paths = extract_mentioned_paths(claim, repo)

    # 2. Untouched-but-claimed files ------------------------------------
    citations: list[Citation] = []
    for mp in mentioned_paths:
        if mp not in changed_paths:
            citations.append(Citation(
                file=mp,
                line_start=1,
                line_end=None,
                reason="claimed-but-untouched: file mentioned in claim but not in diff",
            ))

    # 3. Static AST analysis -------------------------------------------
    ast_flags = check_claim_against_ast(claim, repo, changed_paths)
    stub_flags = detect_stub_implementations(repo, changed_paths)
    test_flags = check_missing_test_coverage(claim, repo, changed_paths)

    for f in ast_flags:
        static_flags.append(f"{f.file}:{f.line}  {f.reason}")
        citations.append(Citation(file=f.file, line_start=f.line, line_end=None, reason=f.reason))

    for f in stub_flags:
        static_flags.append(f"{f.file}:{f.line}  {f.reason}")
        citations.append(Citation(file=f.file, line_start=f.line, line_end=None, reason=f.reason))

    for f in test_flags:
        static_flags.append(f"{f.file}:{f.line}  {f.reason}")
        citations.append(Citation(file=f.file, line_start=f.line, line_end=None, reason=f.reason))

    # 4. Live trace (optional) -----------------------------------------
    trace_flags: list[str] = []
    if run_tests:
        executed = run_tests_with_trace(repo, test_command=test_command)
        trace_flags = check_coverage_gaps(executed, changed_paths, claim)
        for tf in trace_flags:
            if "never executed" in tf:
                path = tf.split(":")[0]
                citations.append(Citation(
                    file=path,
                    line_start=1,
                    line_end=None,
                    reason="changed but never executed during test run",
                ))

    # 5. Score -> Verdict ----------------------------------------------
    lied_count = sum(1 for c in citations if "untouched" in c.reason or "never executed" in c.reason)
    suspicious_count = len(citations) - lied_count

    if lied_count > 0:
        level = VerdictLevel.LIED
        explanation = (
            f"{lied_count} hard discrepanc{'y' if lied_count == 1 else 'ies'} found — "
            "the agent's claim contradicts the actual diff or execution trace."
        )
    elif suspicious_count > 0:
        level = VerdictLevel.SUSPICIOUS
        explanation = (
            f"{suspicious_count} soft flag{'s' if suspicious_count != 1 else ''} found — "
            "the claim is plausible but not fully verified."
        )
    else:
        level = VerdictLevel.PASS
        explanation = "Diff and static analysis are consistent with the claim."

    return VerdictResult(
        level=level,
        claim=claim,
        citations=citations,
        static_flags=static_flags,
        trace_flags=trace_flags,
        diff_summary=diffs,
        explanation=explanation,
    )
