"""Gemini LLM wrapper with structured JSON output, retry logic, and token tracking."""

import json
import time
import re
from typing import Any

import google.generativeai as genai

from backend.config import settings


# Track total tokens used across calls
_total_tokens_used = 0


def get_total_tokens() -> int:
    """Return the running total of tokens consumed."""
    return _total_tokens_used


def reset_token_counter():
    """Reset the running token counter (call at start of each review)."""
    global _total_tokens_used
    _total_tokens_used = 0


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Try to find JSON in code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Try to find a JSON array or object directly
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        return text

    return text


def call_gemini(prompt: str, system_instruction: str = "") -> str:
    """Call Gemini API and return raw text response.

    Args:
        prompt: The user prompt
        system_instruction: System instruction for the model

    Returns:
        Raw text response from the model
    """
    global _total_tokens_used

    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=system_instruction if system_instruction else None,
    )

    last_error = None

    for attempt in range(settings.LLM_MAX_RETRIES):
        try:
            response = model.generate_content(prompt)

            # Track token usage if available
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                _total_tokens_used += getattr(response.usage_metadata, "total_token_count", 0)

            return response.text

        except Exception as e:
            last_error = e
            if attempt < settings.LLM_MAX_RETRIES - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)

    raise RuntimeError(f"Gemini API failed after {settings.LLM_MAX_RETRIES} retries: {last_error}")


def call_gemini_json(prompt: str, system_instruction: str = "") -> Any:
    """Call Gemini and parse the response as JSON.

    Args:
        prompt: The prompt (should instruct model to return JSON)
        system_instruction: System instruction

    Returns:
        Parsed JSON (list or dict)
    """
    raw_response = call_gemini(prompt, system_instruction)

    try:
        json_str = _extract_json(raw_response)
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        # If parsing fails, try one more time with explicit JSON instruction
        retry_prompt = (
            f"Your previous response was not valid JSON. "
            f"Please respond with ONLY a valid JSON array. No other text.\n\n"
            f"Original request:\n{prompt}"
        )
        raw_response = call_gemini(retry_prompt, system_instruction)
        try:
            json_str = _extract_json(raw_response)
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            # Return empty list as fallback
            print(f"Warning: Could not parse LLM response as JSON. Raw: {raw_response[:200]}")
            return []
