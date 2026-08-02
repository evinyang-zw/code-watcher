from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CodeSegment(BaseModel):
    """A single reviewable chunk of code."""

    file_path: str
    hunk_start: int
    hunk_end: int
    old_content: str
    new_content: str
    language: str
    segment_index: int


class ReviewFinding(BaseModel):
    """One finding from reviewing a single segment."""

    finding_id: str = ""
    file_path: str
    line: int
    severity: Literal["critical", "warning", "suggestion", "nit"]
    dimension: Literal["correctness", "style", "security", "performance", "test_coverage"]
    message: str
    suggested_fix: str | None = None
    confidence: float = 0.0


class ReviewResult(BaseModel):
    """Result of reviewing a single segment."""

    segment: CodeSegment
    findings: list[ReviewFinding] = Field(default_factory=list)
    review_duration_ms: int = 0
    tokens_used: int = 0


class FileReviewGroup(BaseModel):
    """Per-file aggregated review results."""

    file_path: str
    review_results: list[ReviewResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0


class FixPatch(BaseModel):
    """A generated fix for a finding."""

    finding: ReviewFinding
    patch_diff: str
    description: str
    test_command: str | None = None
    commit_sha: str | None = None


class EvaluationResult(BaseModel):
    """Result of self-evaluating a fix."""

    patch: FixPatch
    syntax_valid: bool
    tests_pass: bool | None = None
    lint_clean: bool = True
    security_clean: bool = True
    security_findings: list[str] = Field(default_factory=list)
    performance_score: float = 1.0
    performance_issues: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    pre_fix_quality_score: float = 0.0
    post_fix_quality_score: float = 0.0
    quality_delta: float = 0.0
    notes: str = ""


class RunMetadata(BaseModel):
    """Observability metadata for a review run."""

    run_id: str = ""
    start_time: str = ""
    end_time: str = ""
    total_duration_ms: int = 0
    total_tokens_used: int = 0
    model_version: str = ""
    langgraph_checkpoint_count: int = 0
    retry_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
