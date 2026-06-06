"""Self-correction and Quality Filtering Step (Critic/Refiner pattern)."""

import json
from backend.models import DiffFile, Finding
from backend.agent.llm import call_gemini_json
from backend.agent.prompts import (
    SYSTEM_INSTRUCTION,
    FINDINGS_FORMAT,
    build_diff_context,
)

CRITIC_PROMPT = """You are a senior auditor and principal engineer. You are performing a verification pass on draft code review findings.
Your task is to refine these findings to ensure they are high-quality, precise, correct, and represent genuine issues.

Candidate findings (in JSON format):
{raw_findings_json}

Code changes to cross-reference:
{diff_context}

Perform the following refinement steps:
1. FILTER out false positives: Remove any finding that is incorrect, represents a misunderstanding of the code, is a duplicate, or is an overly pedantic/frivolous style nitpick.
2. VERIFY LINE NUMBERS: Look closely at the diff. Ensure the `line_start` and `line_end` in the finding match the actual lines in the diff where the issue exists. If they are incorrect or 0, correct them to point to the exact lines of the code changes.
3. SANITIZE SUGGESTIONS: Review the proposed code suggestions. Ensure they are correct, secure, compile-ready, and follow design best practices. Refine them if needed.
4. Keep the output format exactly as a JSON array of findings.

Return only the final, filtered, and refined JSON array of findings. If all findings are invalid, return an empty array [].
{format_spec}

Respond with ONLY the JSON array, no other text."""


def refine(diff_files: list[DiffFile], raw_findings: list[Finding]) -> list[Finding]:
    """Review, filter, and refine draft findings using an LLM self-correction pass."""
    if not raw_findings:
        return []

    diff_context = build_diff_context(diff_files)
    
    # Serialize raw findings for the LLM
    raw_findings_data = [f.model_dump() for f in raw_findings]
    raw_findings_json = json.dumps(raw_findings_data, indent=2)

    prompt = CRITIC_PROMPT.format(
        raw_findings_json=raw_findings_json,
        diff_context=diff_context,
        format_spec=FINDINGS_FORMAT.replace("<CATEGORY>", "refined"),
    )

    system_instruction = (
        "You are an elite principal software architect. Your job is to audit draft code review comments, "
        "eliminating noise, correcting line associations, and ensuring recommended code fixes are production-ready, secure, and idiomatic."
    )

    try:
        refined_data = call_gemini_json(prompt, system_instruction)
    except Exception as e:
        print(f"Warning: Critic refinement step failed: {e}. Falling back to raw findings.")
        return raw_findings

    refined_findings = []
    if isinstance(refined_data, list):
        for item in refined_data:
            try:
                # Retain the original category if the critic didn't specify one
                category_val = item.get("category")
                # Ensure category matches one of the valid enum values
                if category_val not in ["quality", "bug", "security", "test"]:
                    # map back from the raw finding if possible
                    matching_raw = next(
                        (rf for rf in raw_findings if rf.title == item.get("title")), None
                    )
                    item["category"] = matching_raw.category.value if matching_raw else "quality"
                
                refined_findings.append(Finding(**item))
            except Exception as e:
                print(f"Warning: Could not parse refined finding: {e}. Item was: {item}")

        return refined_findings

    return raw_findings
