"""Git diff parser — extracts per-file stats and mentioned symbols."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import FileDiff


def _is_git_repo(repo: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0 and "true" in res.stdout.strip().lower()
    except Exception:
        return False


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
    if not _is_git_repo(repo):
        raise ValueError(f"Not a git repository: {repo}")

    cmd = ["git", "-C", str(repo), "diff", "--unified=0", "--no-color"]
    if compare:
        cmd += [base, compare]
    else:
        cmd += [base]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    diffs = _parse_unified_diff(result.stdout)
    tracked_paths = {d.path for d in diffs}

    # When comparing working tree against base (default HEAD), also detect untracked new files
    if compare is None:
        untracked_cmd = ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"]
        untracked_res = subprocess.run(untracked_cmd, capture_output=True, text=True)
        if untracked_res.returncode == 0 and untracked_res.stdout.strip():
            for line in untracked_res.stdout.splitlines():
                rel_untracked = Path(line.strip()).as_posix()
                if rel_untracked and rel_untracked not in tracked_paths:
                    file_path = repo / rel_untracked
                    added = 0
                    if file_path.is_file():
                        try:
                            added = sum(1 for _ in file_path.open("rb"))
                        except Exception:
                            added = 1
                    diffs.append(
                        FileDiff(
                            path=rel_untracked,
                            added=added,
                            removed=0,
                            hunks=[f"@@ -0,0 +1,{max(1, added)} @@"],
                        )
                    )

    return diffs


def get_staged_diff(repo_path: str) -> list[FileDiff]:
    """Return diffs for staged (index) changes."""
    repo = Path(repo_path).resolve()
    if not _is_git_repo(repo):
        raise ValueError(f"Not a git repository: {repo}")
    cmd = ["git", "-C", str(repo), "diff", "--cached", "--unified=0", "--no-color"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff --cached failed: {result.stderr.strip()}")
    return _parse_unified_diff(result.stdout)


_EXTENSION_PATTERN = (
    r"[\w./\-]+\.(?:py|tsx?|jsx?|vue|svelte|mjs|cjs|go|rs|java|rb|cs|cpp|c|h|"
    r"json|ya?ml|toml|sql|html|css|scss|sh)"
)


def extract_mentioned_paths(claim: str, repo_path: str) -> list[str]:
    """
    Scan the claim text for file paths that actually exist in the repo.
    Handles bare filenames, dotted module paths, and slash-separated paths.
    Always returns normalized POSIX paths.
    """
    repo = Path(repo_path).resolve()
    candidates: list[str] = []

    # match things that look like paths
    for m in re.finditer(_EXTENSION_PATTERN, claim, re.I):
        raw = m.group()
        # try exact match first
        p = repo / raw
        if p.exists():
            candidates.append(Path(raw).as_posix())
            continue
        # search recursively
        hits = list(repo.rglob(Path(raw).name))
        if hits:
            candidates.append(hits[0].relative_to(repo).as_posix())

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
            current = FileDiff(path=Path(m.group(2)).as_posix(), added=0, removed=0)
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
