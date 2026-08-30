import json
import re
import requests

from .ai_helpers import GROQ_API_URL, GROQ_MODEL, MCQGenerationError, RateLimitError, _parse_retry_after


NOTES_SYSTEM_PROMPT = """You create detailed but exam-focused revision slide content for CBSE students.
Follow the exact JSON structure requested. Bullets can be a full short sentence (up to ~25 words) when
the concept needs it, but avoid long multi-sentence paragraphs. Include the "why"/mechanism behind
concepts, not just labels -- a student should be able to understand and answer questions from these
notes alone, without needing the textbook. Add brief explanations, examples, and numbers/formulas where
relevant. Be factually accurate to the latest CBSE/NCERT syllabus. Do not invent specific PYQ years if
unsure -- use "CBSE Board Question" instead."""


def build_notes_prompt(subject_name, chapter, class_level, num_pyq=2):
    return f"""Create detailed, exam-focused revision slide content for:
Subject: {subject_name}
Class: {class_level}
Chapter: {chapter}
Board: CBSE 2026-27

Return ONLY valid JSON (no markdown, no code fences) matching this exact schema:

{{
  "title": "short chapter title",
  "tagline": "one-line tagline, max 10 words",
  "sections": [
    {{
      "heading": "SECTION TITLE (max 6 words)",
      "bullets": ["explanatory bullet, up to 25 words, can include a brief reason/mechanism/example", "..."],
      "formula": "optional equation/definition line, or null",
      "table": {{"headers": ["Col1","Col2","Col3"], "rows": [["a","b","c"], ["..."]]}}  or null
    }}
  ],
  "pyqs": [
    {{"years": "CBSE 2019, 2021, 2023", "question": "question text under 40 words", "options": ["(a) ...","(b) ...","(c) ...","(d) ..."] or null}}
  ],
  "revision_points": ["important fact, one line, 5-6 total"],
  "common_mistakes": ["mistake students make, one line, 3-4 total"]
}}

Include 6-10 sections covering the WHOLE chapter in depth (every major concept, sub-topic, definition,
cause/effect, and named example from the syllabus) -- do not skip topics for the sake of brevity.
Each section should have 3-6 bullets. Use tables for anything with categories/types/comparisons.
Include exactly {num_pyq} items in "pyqs". Output raw JSON only, no extra commentary."""


def generate_notes_via_groq(api_key, subject_name, chapter, class_level, num_pyq=2):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": NOTES_SYSTEM_PROMPT},
            {"role": "user", "content": build_notes_prompt(subject_name, chapter, class_level, num_pyq)},
        ],
        "temperature": 0.6,
        "max_tokens": 7500,
    }
    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)

    if response.status_code == 429:
        retry_after = _parse_retry_after(response.text)
        raise RateLimitError("Rate limited by Groq", retry_after)
    if response.status_code != 200:
        raise MCQGenerationError(f"Groq API error ({response.status_code}): {response.text}")

    data = response.json()
    message = data['choices'][0]['message']
    text = (message.get('content') or '').strip()

    if not text:
        finish_reason = data['choices'][0].get('finish_reason', 'unknown')
        raise MCQGenerationError(
            f"AI returned an empty response (finish_reason: {finish_reason}). Try again."
        )

    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise MCQGenerationError(f"Could not parse AI response as JSON: {e}\nRaw response:\n{text[:500]}")
