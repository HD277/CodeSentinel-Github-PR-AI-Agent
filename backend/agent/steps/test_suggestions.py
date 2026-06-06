"""Step 4: Test Suggestions — missing coverage, edge case ideas."""

from backend.models import DiffFile, Finding
from backend.agent.llm import call_gemini_json
from backend.agent.prompts import (
    SYSTEM_INSTRUCTION,
    TEST_PROMPT,
    FINDINGS_FORMAT,
    build_diff_context,
)


def analyze(diff_files: list[DiffFile]) -> list[Finding]:
    """Suggest missing tests for the diff files."""
    if not diff_files:
        return []

    diff_context = build_diff_context(diff_files)

    prompt = TEST_PROMPT.format(
        diff_context=diff_context,
        format_spec=FINDINGS_FORMAT.replace("<CATEGORY>", "test"),
    )

    raw_findings = call_gemini_json(prompt, SYSTEM_INSTRUCTION)

    findings = []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            try:
                item["category"] = "test"
                findings.append(Finding(**item))
            except Exception as e:
                print(f"Warning: Could not parse test finding: {e}")

    return findings
