"""Core data models for Verdict."""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VerdictLevel(str, Enum):
    PASS = "PASS"
    SUSPICIOUS = "SUSPICIOUS"
    LIED = "LIED"
    ERROR = "ERROR"


class Citation(BaseModel):
    file: str
    line_start: int
    line_end: Optional[int] = None
    reason: str

    def __str__(self) -> str:
        loc = f"{self.file}:{self.line_start}"
        if self.line_end is not None and self.line_end != self.line_start:
            loc += f"-{self.line_end}"
        return f"{loc}  \u2014  {self.reason}"


class FileDiff(BaseModel):
    path: str
    added: int
    removed: int
    hunks: list[str] = Field(default_factory=list)


class VerdictResult(BaseModel):
    level: VerdictLevel
    claim: str
    citations: list[Citation] = Field(default_factory=list)
    static_flags: list[str] = Field(default_factory=list)
    trace_flags: list[str] = Field(default_factory=list)
    diff_summary: list[FileDiff] = Field(default_factory=list)
    explanation: str

    def to_dict(self) -> dict:
        return {
            "verdict": self.level.value,
            "claim": self.claim,
            "explanation": self.explanation,
            "citations": [c.model_dump() for c in self.citations],
            "static_flags": self.static_flags,
            "trace_flags": self.trace_flags,
            "diff_summary": [d.model_dump() for d in self.diff_summary],
        }