"""Step 1: Code Quality Review — naming, structure, complexity, readability."""

from backend.models import DiffFile, Finding
from backend.agent.llm import call_gemini_json
from backend.agent.prompts import (
    SYSTEM_INSTRUCTION,
    QUALITY_PROMPT,
    FINDINGS_FORMAT,
    build_diff_context,
)


def analyze(diff_files: list[DiffFile]) -> list[Finding]:
    """Run code quality analysis on the diff files."""
    if not diff_files:
        return []

    diff_context = build_diff_context(diff_files)

    prompt = QUALITY_PROMPT.format(
        diff_context=diff_context,
        format_spec=FINDINGS_FORMAT.replace("<CATEGORY>", "quality"),
    )

    raw_findings = call_gemini_json(prompt, SYSTEM_INSTRUCTION)

    findings = []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            try:
                item["category"] = "quality"
                findings.append(Finding(**item))
            except Exception as e:
                print(f"Warning: Could not parse quality finding: {e}")

    return findings
