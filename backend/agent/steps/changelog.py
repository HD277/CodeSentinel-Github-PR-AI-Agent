"""Step 5: Non-Technical Changelog Generator — Translate diff to stakeholder release notes."""

from backend.models import DiffFile
from backend.agent.llm import call_gemini
from backend.agent.prompts import (
    CHANGELOG_PROMPT,
    build_diff_context,
)


def generate(diff_files: list[DiffFile]) -> str:
    """Generate high-level, business-oriented release notes for the changes."""
    if not diff_files:
        return "No reviewable code changes in this Pull Request."

    diff_context = build_diff_context(diff_files)

    prompt = CHANGELOG_PROMPT.format(diff_context=diff_context)

    system_instruction = (
        "You are an expert technical product manager specializing in developer relations. "
        "You explain complex software changes in a concise, business-oriented manner for non-technical stakeholders."
    )

    try:
        return call_gemini(prompt, system_instruction)
    except Exception as e:
        print(f"Warning: Changelog generation failed: {e}")
        return "Failed to generate high-level changelog."
