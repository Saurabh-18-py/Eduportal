import json
import re

import requests
from pypdf import PdfReader

from mocktest.ai_helpers import (
    GROQ_API_URL,
    GROQ_MODEL,
    RateLimitError,
    InvalidAPIKeyError,
    MCQGenerationError,
)


def _parse_retry_after(error_text):
    match = re.search(r'try again in ([\d.]+)s', error_text)
    return float(match.group(1)) if match else 20.0


def extract_first_page_text(file_obj):
    """Pulls text off the first page of an uploaded PDF, for AI metadata detection."""
    file_obj.seek(0)
    text = ""
    try:
        reader = PdfReader(file_obj)
        if reader.pages:
            text = reader.pages[0].extract_text() or ""
    except Exception:
        text = ""
    finally:
        file_obj.seek(0)  # rewind so the file can still be saved to the model field afterwards
    return text


def detect_pyq_metadata(api_key, filename, pdf_text, known_subjects):
    """
    known_subjects: list of (id, name, class_level) tuples for every existing
    Subject, so the AI matches against what's actually in the database
    instead of inventing a new subject name. The filename is passed too,
    since many CBSE papers don't print the year on the page itself, but a
    user can name the file with the year in it (e.g. "Science_2023_Set1.pdf").
    """
    subjects_list = "\n".join(
        f"- {name} (Class {class_level})" for _id, name, class_level in known_subjects
    )
    body_text = pdf_text[:3000].strip() or "(no extractable text - this may be a scanned/image-only PDF)"

    prompt = f"""This is a CBSE previous-year board exam question paper PDF.

Filename: {filename}

First page text:
---
{body_text}
---

Extract these details about the paper. Check BOTH the filename and the page text -
the exam year in particular is often only in the filename (many official CBSE papers
don't print the calendar year on the page itself, only a "Series" code):
- class_level: 9, 10, 11, or 12 (as a number), or null if unclear
- subject: the BARE subject name only, exactly as it appears before " (Class" in this list
  (do NOT include the "(Class N)" part in your answer) - match to one of:
{subjects_list}
- year: the 4-digit exam year (e.g. 2023), or null if it truly isn't in the filename or the text
- set_label: the paper's Set number. CBSE papers often show a "Code Number" or "Series"
  like "32/4/1" or "31-4-3" (in the filename and/or on the page) - the LAST number in that
  code is almost always the Set number, so "32/4/1" means Set 1, "31-4-3" means Set 3.
  Also check for it spelled out directly (e.g. "SET-1", "Set A"). Respond with just the
  number/letter (e.g. "1", "A"), or "" if you truly can't find any clue.

Respond with ONLY a JSON object, no other text, no markdown fences. Example - note "subject"
has NO "(Class ...)" in it even though the list above shows it that way, and "set_label" is
just the bare number/letter:
{{"class_level": 10, "subject": "Science", "year": 2023, "set_label": "1"}}"""

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 300,
            "reasoning_effort": "low",
        },
        timeout=60,
    )

    if response.status_code == 429:
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
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise MCQGenerationError(f"Could not parse metadata JSON: {e}\nRaw: {text[:300]}")


def detect_pyq_metadata_with_rotation(api_keys, key_index, filename, pdf_text, known_subjects, on_rotate=None):
    """Same key-rotation pattern used elsewhere in the project - tries each key until one works."""
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            result = detect_pyq_metadata(api_keys[idx], filename, pdf_text, known_subjects)
            key_index[0] = idx
            return result
        except (RateLimitError, InvalidAPIKeyError) as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error
