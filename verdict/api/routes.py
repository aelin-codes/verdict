"""REST API routes."""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from verdict.core import analyze
from verdict.core.models import VerdictResult

router = APIRouter()


# ── Request / Response schemas ─────────────────────────────────────────

class CheckRequest(BaseModel):
    repo_path: str = Field(
        ...,
        description="Absolute path to the git repository on the server.",
        example="/home/user/projects/my-app",
    )
    claim: str = Field(
        ...,
        description="The agent's natural-language completion statement.",
        example="Refactored the auth module and added session expiry.",
    )
    base_ref: str = Field(
        default="HEAD",
        description="Git ref to diff against.",
    )
    compare_ref: Optional[str] = Field(
        default=None,
        description="Optional second ref (e.g. 'origin/main').",
    )
    run_tests: bool = Field(
        default=False,
        description="Execute the test suite under sys.settrace for live coverage.",
    )
    test_command: Optional[list[str]] = Field(
        default=None,
        description="Override the default pytest command, e.g. ['python', '-m', 'pytest', '-x'].",
    )


class CitationOut(BaseModel):
    file: str
    line_start: int
    line_end: Optional[int]
    reason: str


class FileDiffOut(BaseModel):
    path: str
    added: int
    removed: int


class CheckResponse(BaseModel):
    verdict: str
    claim: str
    explanation: str
    citations: list[CitationOut]
    static_flags: list[str]
    trace_flags: list[str]
    diff_summary: list[FileDiffOut]


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": "0.1.0"}


@router.post(
    "/check",
    response_model=CheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["verdict"],
    summary="Run a verdict check on a local repository",
)
def check(req: CheckRequest) -> CheckResponse:
    """
    Analyse a git repository against an agent's completion claim.

    Returns **PASS**, **SUSPICIOUS**, or **LIED** with file:line citations.
    """
    if not os.path.isdir(req.repo_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"repo_path does not exist or is not a directory: {req.repo_path}",
        )

    try:
        result: VerdictResult = analyze(
            repo_path=req.repo_path,
            claim=req.claim,
            base_ref=req.base_ref,
            compare_ref=req.compare_ref,
            run_tests=req.run_tests,
            test_command=req.test_command,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    raw = result.to_dict()
    return CheckResponse(
        verdict=raw["verdict"],
        claim=raw["claim"],
        explanation=raw["explanation"],
        citations=[CitationOut(**c) for c in raw["citations"]],
        static_flags=raw["static_flags"],
        trace_flags=raw["trace_flags"],
        diff_summary=[FileDiffOut(**d) for d in raw["diff_summary"]],
    )


@router.get(
    "/verdicts",
    tags=["verdict"],
    summary="List all possible verdict levels",
)
def list_verdicts() -> dict:
    """Return metadata about the three verdict levels."""
    return {
        "levels": [
            {
                "name": "PASS",
                "color": "green",
                "description": "Diff and static analysis are consistent with the claim.",
            },
            {
                "name": "SUSPICIOUS",
                "color": "orange",
                "description": "Claim is plausible but not fully verified — soft flags raised.",
            },
            {
                "name": "LIED",
                "color": "red",
                "description": "Hard evidence the claim contradicts the diff or execution trace.",
            },
        ]
    }
