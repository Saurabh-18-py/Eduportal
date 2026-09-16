import json

import requests

from mocktest.ai_helpers import (
    GROQ_API_URL,
    GROQ_MODEL,
    RateLimitError,
    InvalidAPIKeyError,
    MCQGenerationError,
    _try_salvage_json_array,
)


def _request_notes_from_groq(api_key, subject_name, chapter, class_level):
    """
    Asks Groq for detailed, exam-ready notes for one chapter: a list of
    sections, each with a heading and a detailed explanation that includes
    at least one worked example where the topic allows for it (numericals,
    formulas, historical dates, etc).
    """
    prompt = f"""You are writing detailed study notes for Indian CBSE Class {class_level} {subject_name}, chapter: "{chapter}".

Write comprehensive notes covering every important concept in this chapter, broken into
clear sections. For each section:
- Give a short, clear heading (a sub-topic within the chapter).
- Write a DETAILED explanation in simple language a Class {class_level} student can follow.
- Include at least one concrete example, worked problem, or illustration wherever the
  sub-topic allows it (e.g. a solved numerical, a real-world example, a labelled process).

Stay strictly within the depth of the official CBSE NCERT Class {class_level} syllabus for
this exact chapter - do not bring in concepts from a higher or lower class.

Respond with ONLY a JSON array, no other text, no markdown code fences. Format:
[
  {{
    "heading": "Sub-topic name",
    "content": "Detailed explanation including at least one example, written as plain text (use \\n for line breaks between paragraphs or example steps)."
  }}
]

Cover the whole chapter - use as many sections as needed (typically 5-10)."""

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 8000,
            "reasoning_effort": "low",
        },
        timeout=90,
    )

    if response.status_code == 429:
        from .pdf_ai import _parse_retry_after
        raise RateLimitError(f"Rate limited: {response.text}", _parse_retry_after(response.text))

    if response.status_code == 401:
        raise InvalidAPIKeyError(f"Invalid/revoked API key: {response.text}")

    if response.status_code != 200:
        raise MCQGenerationError(f"Groq API error ({response.status_code}): {response.text}")

    data = response.json()
    text = data['choices'][0]['message']['content'].strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        sections = json.loads(text)
    except json.JSONDecodeError as e:
        sections = _try_salvage_json_array(text)
        if sections is None:
            raise MCQGenerationError(f"Could not parse notes JSON: {e}\nRaw response:\n{text[:500]}")

    valid_sections = [
        s for s in sections
        if isinstance(s, dict) and s.get('heading') and s.get('content')
    ]

    if not valid_sections:
        raise MCQGenerationError("AI response had no valid, well-formed sections after filtering.")

    return valid_sections, response.headers


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def generate_notes_batch_with_meta(api_key, subject_name, chapter, class_level):
    sections, headers = _request_notes_from_groq(api_key, subject_name, chapter, class_level)
    meta = {
        'remaining_tokens': _safe_int(headers.get('x-ratelimit-remaining-tokens')),
        'remaining_requests': _safe_int(headers.get('x-ratelimit-remaining-requests')),
    }
    return sections, meta


def generate_notes_batch_with_rotation(api_keys, key_index, subject_name, chapter, class_level, on_rotate=None):
    """Same key-rotation pattern used elsewhere in the project."""
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            sections, meta = generate_notes_batch_with_meta(api_keys[idx], subject_name, chapter, class_level)
            key_index[0] = idx
            return sections, meta
        except (RateLimitError, InvalidAPIKeyError) as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error
