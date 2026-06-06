from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────

class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"
    suggestion = "suggestion"


class Category(str, Enum):
    quality = "quality"
    bug = "bug"
    security = "security"
    test = "test"


# ── Request Models ─────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    pr_url: str = Field(..., description="Full GitHub PR URL, e.g. https://github.com/owner/repo/pull/123")


# ── Core Finding Model ─────────────────────────────────────────────

class Finding(BaseModel):
    category: Category
    severity: Severity
    file: str = Field(..., description="File path relative to repo root")
    line_start: int = Field(0, description="Starting line number (0 if unknown)")
    line_end: int = Field(0, description="Ending line number (0 if unknown)")
    title: str = Field(..., description="Short title of the issue")
    description: str = Field(..., description="Detailed explanation")
    suggestion: str = Field("", description="Recommended fix or improvement")
    code_snippet: str = Field("", description="Relevant code snippet")


# ── Review Stats ───────────────────────────────────────────────────

class ReviewStats(BaseModel):
    files_reviewed: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    review_time_seconds: float = 0.0
    tokens_used: int = 0


# ── PR Metadata ────────────────────────────────────────────────────

class PRMetadata(BaseModel):
    url: str
    title: str = ""
    author: str = ""
    description: str = ""
    base_branch: str = ""
    head_branch: str = ""
    repo_full_name: str = ""
    pr_number: int = 0
    files_changed: int = 0


# ── Full Review Response ───────────────────────────────────────────

class ReviewResponse(BaseModel):
    id: Optional[str] = None
    pr: PRMetadata
    findings: list[Finding] = []
    stats: ReviewStats = ReviewStats()
    summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.critical)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.warning)


# ── Diff File Model (internal) ─────────────────────────────────────

class DiffFile(BaseModel):
    filename: str
    language: str = ""
    additions: int = 0
    deletions: int = 0
    patch: str = ""  # The raw diff content for this file
    added_lines: list[str] = []
    status: str = "modified"  # added, removed, modified, renamed


# ── Review History Item (for listing) ──────────────────────────────

class ReviewHistoryItem(BaseModel):
    id: str
    pr_url: str
    pr_title: str
    repo: str
    total_findings: int
    critical_count: int
    warning_count: int
    review_time_seconds: float
    created_at: str
