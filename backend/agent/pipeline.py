# Orchestrate the review pipeline steps

import time
import uuid

from backend.models import DiffFile, ReviewResponse, ReviewStats, PRMetadata, Finding
from backend.agent.llm import call_gemini, get_total_tokens, reset_token_counter
from backend.agent.prompts import SYSTEM_INSTRUCTION, SUMMARY_PROMPT
from backend.agent.steps import quality, bugs, security, test_suggestions


def run_review(diff_files: list[DiffFile], pr_metadata: PRMetadata) -> ReviewResponse:
    # runs the code review steps sequentially
    start_time = time.time()
    reset_token_counter()

    all_findings: list[Finding] = []
    step_errors: list[str] = []

    # quality check
    print("  [1/4] Analyzing code quality...")
    try:
        quality_findings = quality.analyze(diff_files)
        all_findings.extend(quality_findings)
        print(f"         Found {len(quality_findings)} quality issues")
    except Exception as e:
        step_errors.append(f"Quality step failed: {e}")
        print(f"         ⚠ Quality step failed: {e}")

    # bug check
    print("  [2/4] Detecting bugs...")
    try:
        bug_findings = bugs.analyze(diff_files)
        all_findings.extend(bug_findings)
        print(f"         Found {len(bug_findings)} potential bugs")
    except Exception as e:
        step_errors.append(f"Bug detection failed: {e}")
        print(f"         ⚠ Bug detection failed: {e}")

    # security scan
    print("  [3/4] Scanning for security issues...")
    try:
        security_findings = security.analyze(diff_files)
        all_findings.extend(security_findings)
        print(f"         Found {len(security_findings)} security concerns")
    except Exception as e:
        step_errors.append(f"Security scan failed: {e}")
        print(f"         ⚠ Security scan failed: {e}")

    # missing tests suggestions
    print("  [4/4] Generating test suggestions...")
    try:
        test_findings = test_suggestions.analyze(diff_files)
        all_findings.extend(test_findings)
        print(f"         Found {len(test_findings)} test suggestions")
    except Exception as e:
        step_errors.append(f"Test suggestions failed: {e}")
        print(f"         ⚠ Test suggestions failed: {e}")

    elapsed = time.time() - start_time

    # generate text summary
    summary = _generate_summary(pr_metadata, all_findings)

    # compute stats
    total_additions = sum(f.additions for f in diff_files)
    total_deletions = sum(f.deletions for f in diff_files)

    stats = ReviewStats(
        files_reviewed=len(diff_files),
        total_additions=total_additions,
        total_deletions=total_deletions,
        review_time_seconds=round(elapsed, 2),
        tokens_used=get_total_tokens(),
    )

    review = ReviewResponse(
        id=str(uuid.uuid4()),
        pr=pr_metadata,
        findings=all_findings,
        stats=stats,
        summary=summary,
    )

    print(f"\n  ✓ Review complete: {len(all_findings)} findings in {elapsed:.1f}s")

    if step_errors:
        print(f"  ⚠ {len(step_errors)} step(s) had errors")

    return review


def _generate_summary(pr_metadata: PRMetadata, findings: list[Finding]) -> str:
    # call LLM to summarize the findings list
    if not findings:
        return "No issues found in this pull request. The code changes look clean and well-structured."

    critical = sum(1 for f in findings if f.severity.value == "critical")
    warnings = sum(1 for f in findings if f.severity.value == "warning")
    info = sum(1 for f in findings if f.severity.value == "info")
    suggestions = sum(1 for f in findings if f.severity.value == "suggestion")

    # Get top 3 most important findings for context
    priority_order = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}
    sorted_findings = sorted(findings, key=lambda f: priority_order.get(f.severity.value, 4))
    top_findings = "\n".join(
        f"- [{f.severity.value.upper()}] {f.title} in {f.file}"
        for f in sorted_findings[:5]
    )

    prompt = SUMMARY_PROMPT.format(
        pr_title=pr_metadata.title,
        files_changed=pr_metadata.files_changed,
        total_findings=len(findings),
        critical=critical,
        warnings=warnings,
        info=info,
        suggestions=suggestions,
        top_findings=top_findings,
    )

    try:
        return call_gemini(prompt, SYSTEM_INSTRUCTION)
    except Exception:
        # Fallback summary if LLM fails
        parts = []
        if critical:
            parts.append(f"{critical} critical issue(s)")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        if info:
            parts.append(f"{info} informational note(s)")
        if suggestions:
            parts.append(f"{suggestions} suggestion(s)")
        return f"Found {', '.join(parts)} across the code changes."
