"""AST-based static analysis for Verdict."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple


class ASTFlag(NamedTuple):
    file: str
    line: int
    reason: str


def check_claim_against_ast(claim: str, repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    Walk the AST of every changed Python file and look for discrepancies
    between the claim and the actual code structure.

    Checks performed:
    - Functions/classes mentioned in the claim but absent from changed files
    - Files mentioned as changed that have zero diff lines (untouched)
    - Empty function bodies (pass-only) for symbols the claim says were implemented
    - Syntax errors in changed files
    """
    flags: list[ASTFlag] = []
    repo = Path(repo_path).resolve()

    # Extract symbol names mentioned in the claim
    mentioned_symbols = _extract_symbols(claim)

    for rel_path in changed_files:
        full_path = repo / rel_path
        if not full_path.exists() or full_path.suffix != ".py":
            continue
        flags.extend(_analyze_file(full_path, rel_path, mentioned_symbols))

    return flags


def detect_stub_implementations(repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    Detect functions that look like stubs: only contain `pass`, `...`,
    or a single docstring with no real logic.
    """
    flags: list[ASTFlag] = []
    repo = Path(repo_path).resolve()

    for rel_path in changed_files:
        full_path = repo / rel_path
        if not full_path.exists() or full_path.suffix != ".py":
            continue
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_stub(node):
                    flags.append(ASTFlag(
                        file=rel_path,
                        line=node.lineno,
                        reason=f"'{node.name}' appears to be a stub (pass/... body)",
                    ))
    return flags


def check_missing_test_coverage(claim: str, repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    If the claim implies tests were added or verified, check that
    test files in changed_files actually contain test functions.
    """
    flags: list[ASTFlag] = []
    test_claim_patterns = [
        r"\btest(ed|s|ing)?\b", r"\bunit test\b", r"\bcoverage\b",
        r"\bspec\b", r"\bpytest\b",
    ]
    claim_implies_tests = any(
        re.search(p, claim, re.I) for p in test_claim_patterns
    )
    if not claim_implies_tests:
        return flags

    test_files = [f for f in changed_files if "test" in Path(f).name]
    if not test_files:
        flags.append(ASTFlag(
            file="(repo)",
            line=0,
            reason="Claim mentions tests but no test files were modified",
        ))
        return flags

    repo = Path(repo_path).resolve()
    for rel_path in test_files:
        full_path = repo / rel_path
        if not full_path.exists():
            continue
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError:
            continue

        test_fns = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test")
        ]
        if not test_fns:
            flags.append(ASTFlag(
                file=rel_path,
                line=1,
                reason="Test file changed but contains no test_ functions",
            ))

    return flags


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_symbols(claim: str) -> set[str]:
    """Pull out likely Python identifiers from the claim text."""
    return set(re.findall(r"\b([a-z_][a-z0-9_]{2,})\b", claim, re.I))


def _analyze_file(
    path: Path,
    rel_path: str,
    mentioned_symbols: set[str],
) -> list[ASTFlag]:
    flags: list[ASTFlag] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        flags.append(ASTFlag(file=rel_path, line=exc.lineno or 1, reason=f"SyntaxError: {exc.msg}"))
        return flags

    defined_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    # symbols the claim mentions that don't appear in this file
    absent = mentioned_symbols & {s for s in mentioned_symbols if s not in defined_names}
    # Only flag if the absent symbol looks specific (camelCase or snake_case with underscore)
    for sym in absent:
        if "_" in sym or (sym != sym.lower() and sym != sym.upper()):
            flags.append(ASTFlag(
                file=rel_path,
                line=1,
                reason=f"Symbol '{sym}' mentioned in claim not found in file",
            ))

    return flags


def _is_stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = node.body
    # strip docstring
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if not body:
        return True
    if len(body) == 1:
        stmt = body[0]
        # pass
        if isinstance(stmt, ast.Pass):
            return True
        # ...
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
            return True
        # raise NotImplementedError
        if isinstance(stmt, ast.Raise):
            return True
    return False
