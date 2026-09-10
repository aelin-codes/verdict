"""AST-based and polyglot static analysis for Verdict."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple


class ASTFlag(NamedTuple):
    file: str
    line: int
    reason: str


_STOP_WORDS = {
    "add", "added", "adding",
    "implement", "implemented", "implementing",
    "create", "created", "creating",
    "fix", "fixed", "fixing",
    "update", "updated", "updating",
    "refactor", "refactored", "refactoring",
    "remove", "removed", "removing",
    "delete", "deleted", "deleting",
    "change", "changed", "changing",
    "allow", "allowed", "allowing",
    "ensure", "ensured", "ensuring",
    "support", "supported", "supporting",
    "verify", "verified", "verifying",
    "test", "tests", "tested", "testing",
    "feature", "features",
    "bug", "bugs",
    "module", "modules",
    "file", "files",
    "class", "classes",
    "function", "functions",
    "method", "methods",
    "service", "services",
    "component", "components",
    "endpoint", "endpoints",
    "router", "routers",
    "model", "models",
    "schema", "schemas",
    "util", "utils", "utility", "utilities",
    "config", "configuration",
    "valid", "real", "proper", "true", "false",
}


def check_claim_against_ast(claim: str, repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    Walk the code structure of every changed file and look for discrepancies
    between the claim and the actual code structure.
    """
    flags: list[ASTFlag] = []
    repo = Path(repo_path).resolve()

    exclude_stems = {Path(f).stem.lower() for f in changed_files} | {Path(f).name.lower() for f in changed_files}
    mentioned_symbols = _extract_symbols(claim, exclude_stems=exclude_stems)

    for rel_path in changed_files:
        full_path = repo / rel_path
        if not full_path.exists():
            continue
        flags.extend(_analyze_file(full_path, rel_path, mentioned_symbols))

    return flags


def detect_stub_implementations(repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    Detect functions/methods that look like stubs: only contain pass, ...,
    empty braces {}, or a single docstring/comment with no real logic.
    """
    flags: list[ASTFlag] = []
    repo = Path(repo_path).resolve()

    for rel_path in changed_files:
        full_path = repo / rel_path
        if not full_path.exists():
            continue

        if full_path.suffix == ".py":
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
        else:
            # Polyglot fallback: lightweight detection of empty function bodies in TS/JS/etc.
            try:
                source = full_path.read_text(encoding="utf-8", errors="ignore")
                pattern = (
                    r"(?:function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)|"
                    r"([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)\s*"
                    r"(?::\s*[^{]+)?\{\s*(?:\/\/[^\n]*|\/\*.*?\*\/)?\s*\}"
                )
                for m in re.finditer(pattern, source, re.DOTALL):
                    fn_name = m.group(1) or m.group(2) or "function"
                    lineno = source[:m.start()].count("\n") + 1
                    flags.append(ASTFlag(
                        file=rel_path,
                        line=lineno,
                        reason=f"'{fn_name}' appears to be a stub (empty body)",
                    ))
            except Exception:
                continue

    return flags


def check_missing_test_coverage(claim: str, repo_path: str, changed_files: list[str]) -> list[ASTFlag]:
    """
    If the claim implies tests were added or verified, check that
    test files in changed_files actually contain test functions.
    """
    flags: list[ASTFlag] = []
    test_claim_patterns = [
        r"\btest(ed|s|ing)?\b", r"\bunit test\b", r"\bcoverage\b",
        r"\bspec\b", r"\bpytest\b", r"\bjest\b",
    ]
    claim_implies_tests = any(
        re.search(p, claim, re.I) for p in test_claim_patterns
    )
    if not claim_implies_tests:
        return flags

    test_files = [f for f in changed_files if "test" in Path(f).name.lower() or "spec" in Path(f).name.lower()]
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
            source = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if full_path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=rel_path)
                test_fns = [
                    n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name.startswith("test")
                ]
            except SyntaxError:
                continue

            if not test_fns:
                flags.append(ASTFlag(
                    file=rel_path,
                    line=1,
                    reason="Test file changed but contains no test_ functions",
                ))
        else:
            # JS/TS/Go/Rust polyglot test pattern match
            has_tests = bool(re.search(r"\b(?:test|it|describe)\s*\(|func\s+Test|#\[test\]", source))
            if not has_tests:
                flags.append(ASTFlag(
                    file=rel_path,
                    line=1,
                    reason="Test file changed but contains no test/spec definitions",
                ))

    return flags


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_symbols(claim: str, exclude_stems: set[str] | None = None) -> set[str]:
    """Pull out likely identifiers from the claim text, excluding stop words and file names."""
    raw = set(re.findall(r"\b([a-z_][a-z0-9_]{2,})\b", claim, re.I))
    stems = {s.lower() for s in (exclude_stems or set())}
    return {
        s for s in raw
        if s.lower() not in _STOP_WORDS and s.lower() not in stems
    }


def _analyze_file(
    path: Path,
    rel_path: str,
    mentioned_symbols: set[str],
) -> list[ASTFlag]:
    flags: list[ASTFlag] = []

    if path.suffix == ".py":
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
    else:
        # Lightweight polyglot identifier extractor for TS/JS/Go/Rust
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            defined_names = set(re.findall(
                r"\b(?:class|interface|function|const|let|var|type|enum|def|func|fn)\s+([a-zA-Z0-9_]+)",
                source,
            ))
            # Also catch class methods / object methods
            defined_names |= set(re.findall(r"\b([a-zA-Z0-9_]+)\s*\([^)]*\)\s*[:{]", source))
        except Exception:
            return flags

    # symbols the claim mentions that don't appear in this file
    absent = mentioned_symbols & {s for s in mentioned_symbols if s not in defined_names}
    for sym in absent:
        # Only flag if symbol looks like an identifier (snake_case with underscore or camelCase)
        is_camel = bool(re.match(r"^[a-z]+[A-Z][a-zA-Z0-9]*$", sym)) or (
            bool(re.match(r"^[A-Z][a-zA-Z0-9]+$", sym)) and sym.lower() not in _STOP_WORDS
        )
        is_snake = "_" in sym
        if is_snake or is_camel:
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

