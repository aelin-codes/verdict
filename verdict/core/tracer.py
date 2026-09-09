"""Live execution tracer using sys.settrace."""
from __future__ import annotations

import sys
import importlib
import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Callable


class CoverageTrace:
    """
    A lightweight sys.settrace-based coverage recorder.

    Usage::

        tracer = CoverageTrace(watch_dir="/repo/src")
        tracer.start()
        # ... run code ...
        tracer.stop()
        hit = tracer.executed_lines  # {"src/auth.py": {10, 11, 14}}
    """

    def __init__(self, watch_dir: str):
        self.watch_dir = str(Path(watch_dir).resolve())
        self.executed_lines: dict[str, set[int]] = {}
        self._prev_trace: Callable | None = None

    def start(self) -> None:
        self._prev_trace = sys.gettrace()
        sys.settrace(self._trace_calls)

    def stop(self) -> None:
        sys.settrace(self._prev_trace)

    def _trace_calls(self, frame, event, arg):  # noqa: ANN001
        filename = frame.f_code.co_filename
        if not filename.startswith(self.watch_dir):
            return None
        if event == "call":
            return self._trace_lines
        return None

    def _trace_lines(self, frame, event, arg):  # noqa: ANN001
        if event == "line":
            filename = frame.f_code.co_filename
            rel = os.path.relpath(filename, self.watch_dir)
            self.executed_lines.setdefault(rel, set()).add(frame.f_lineno)
        return self._trace_lines


def run_tests_with_trace(
    repo_path: str,
    test_command: list[str] | None = None,
) -> dict[str, set[int]]:
    """
    Run the test suite inside the repo and collect executed lines via
    subprocess + coverage (preferred) or a fresh sys.settrace session.

    Returns a mapping of relative file path -> set of executed line numbers.
    """
    repo = Path(repo_path).resolve()

    # Prefer running pytest with --tb=no for speed
    cmd = test_command or ["python", "-m", "pytest", "--tb=no", "-q"]

    # We emit a small tracing shim so we don't need to instrument the subprocess
    shim = repo / ".verdict_trace_shim.py"
    trace_out = repo / ".verdict_trace.txt"

    shim_code = f'''
import sys, os, json

_executed = {{}}
_watch = {str(repo)!r}

def _trace_calls(frame, event, arg):
    fn = frame.f_code.co_filename
    if fn.startswith(_watch) and event == "call":
        return _trace_lines
    return None

def _trace_lines(frame, event, arg):
    if event == "line":
        fn = frame.f_code.co_filename
        rel = os.path.relpath(fn, _watch)
        _executed.setdefault(rel, []).append(frame.f_lineno)
    return _trace_lines

sys.settrace(_trace_calls)
import atexit

def _dump():
    sys.settrace(None)
    with open({str(trace_out)!r}, "w") as f:
        json.dump({{k: sorted(set(v)) for k,v in _executed.items()}}, f)
atexit.register(_dump)
'''
    try:
        shim.write_text(shim_code)
        env = os.environ.copy()
        env["PYTHONSTARTUP"] = str(shim)
        subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            env=env,
            timeout=120,
        )
        if trace_out.exists():
            import json
            raw = json.loads(trace_out.read_text())
            return {k: set(v) for k, v in raw.items()}
    except Exception:  # noqa: BLE001
        pass
    finally:
        shim.unlink(missing_ok=True)
        trace_out.unlink(missing_ok=True)

    return {}


def check_coverage_gaps(
    executed: dict[str, set[int]],
    changed_files: list[str],
    claim: str,
) -> list[str]:
    """
    Cross-reference executed lines against changed files.
    Returns a list of human-readable flag strings.
    """
    flags: list[str] = []
    for rel_path in changed_files:
        if not rel_path.endswith(".py"):
            continue
        if rel_path not in executed:
            flags.append(f"{rel_path}: changed but never executed during test run")
        else:
            flags.append(f"{rel_path}: executed {len(executed[rel_path])} line(s) under trace")
    return flags
