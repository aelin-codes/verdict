"""Git diff parser — extracts per-file stats and mentioned symbols."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import FileDiff


def get_diff(repo_path: str, base: str = "HEAD", compare: str | None = None) -> list[FileDiff]:
    """
    Return a list of FileDiff objects for every changed file.

    Args:
        repo_path: Absolute or relative path to the git repository root.
        base:      The base ref (default HEAD).
        compare:   Optional second ref (e.g. "origin/main"). When omitted,
                   compares the working tree against *base*.
    """
    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        raise ValueError(f"Not a git repository: {repo}")

    cmd = ["git", "-C", str(repo), "diff", "--unified=0", "--no-color"]
    if compare:
        cmd += [base, compare]
    else:
        cmd += [base]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    return _parse_unified_diff(result.stdout)


def get_staged_diff(repo_path: str) -> list[FileDiff]:
    """Return diffs for staged (index) changes."""
    repo = Path(repo_path).resolve()
    cmd = ["git", "-C", str(repo), "diff", "--cached", "--unified=0", "--no-color"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff --cached failed: {result.stderr.strip()}")
    return _parse_unified_diff(result.stdout)


def extract_mentioned_paths(claim: str, repo_path: str) -> list[str]:
    """
    Scan the claim text for file paths that actually exist in the repo.
    Handles bare filenames, dotted module paths, and slash-separated paths.
    """
    repo = Path(repo_path).resolve()
    candidates: list[str] = []

    # match things that look like paths: foo/bar.py, src/auth/session.py, tokens.py
    for m in re.finditer(r"[\w./\-]+\.(?:py|ts|js|go|rs|java|rb|cs|cpp|c|h)", claim):
        raw = m.group()
        # try exact match first
        p = repo / raw
        if p.exists():
            candidates.append(raw)
            continue
        # search recursively
        hits = list(repo.rglob(Path(raw).name))
        if hits:
            candidates.append(str(hits[0].relative_to(repo)))

    return list(dict.fromkeys(candidates))  # deduplicate, preserve order


# ── internal ────────────────────────────────────────────────────────────────

_FILE_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _parse_unified_diff(raw: str) -> list[FileDiff]:
    diffs: list[FileDiff] = []
    current: FileDiff | None = None

    for line in raw.splitlines():
        m = _FILE_HEADER.match(line)
        if m:
            if current:
                diffs.append(current)
            current = FileDiff(path=m.group(2), added=0, removed=0)
            continue

        if current is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current.added += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.removed += 1

        h = _HUNK_HEADER.match(line)
        if h:
            current.hunks.append(line)

    if current:
        diffs.append(current)

    return diffs
