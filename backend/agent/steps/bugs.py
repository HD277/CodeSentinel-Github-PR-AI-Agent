"""Step 2: Bug Detection — logic errors, edge cases, null refs, off-by-one."""

from backend.models import DiffFile, Finding
from backend.agent.llm import call_gemini_json
from backend.agent.prompts import (
    SYSTEM_INSTRUCTION,
    BUGS_PROMPT,
    FINDINGS_FORMAT,
    build_diff_context,
)


def analyze(diff_files: list[DiffFile]) -> list[Finding]:
    """Run bug detection analysis on the diff files."""
    if not diff_files:
        return []

    diff_context = build_diff_context(diff_files)

    prompt = BUGS_PROMPT.format(
        diff_context=diff_context,
        format_spec=FINDINGS_FORMAT.replace("<CATEGORY>", "bug"),
    )

    raw_findings = call_gemini_json(prompt, SYSTEM_INSTRUCTION)

    findings = []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            try:
                item["category"] = "bug"
                findings.append(Finding(**item))
            except Exception as e:
                print(f"Warning: Could not parse bug finding: {e}")

    return findings
