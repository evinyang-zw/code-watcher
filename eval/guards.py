"""Noise-reduction guards for review findings.

Human reviewers leave at most a handful of comments per PR; a review agent that
emits every nit gets ignored (comment bombing). These guards model a realistic
"publishing policy" so the evaluation can show a before/after: raw model output
vs what would actually be posted.

Guards are applied *after* generation and never see the gold set.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from eval.schema import Finding

SEVERITY_RANK = {"critical": 3, "warning": 2, "suggestion": 1, "nit": 0}


def apply_guard(
    findings: Sequence[Finding],
    *,
    min_severity: str = "warning",
    max_findings: int = 5,
    dedupe: bool = True,
) -> list[Finding]:
    """Filter findings the way a PR-comment policy would.

    - drop findings below ``min_severity`` (a review bot should not post nits);
    - dedupe by (file, rounded line, dimension) to avoid near-duplicates;
    - cap the number of findings per PR so one PR cannot be flooded.
    """
    threshold = SEVERITY_RANK.get(min_severity, 0)
    seen: set[tuple[str, int, str]] = set()
    kept: list[Finding] = []
    for finding in findings:
        if SEVERITY_RANK.get(finding.severity, 0) < threshold:
            continue
        key = (finding.file, finding.line, finding.dimension)
        if dedupe and key in seen:
            continue
        seen.add(key)
        kept.append(finding)
        if len(kept) >= max_findings:
            break
    return kept


def apply_guard_to_all(
    findings_by_instance: Iterable[Iterable[Finding]],
    **options: object,
) -> list[list[Finding]]:
    return [apply_guard(list(findings), **options) for findings in findings_by_instance]  # type: ignore[arg-type]
