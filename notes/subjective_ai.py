import json

import requests

from mocktest.ai_helpers import (
    GROQ_API_URL,
    GROQ_MODEL,
    RateLimitError,
    InvalidAPIKeyError,
    MCQGenerationError,
    _try_salvage_json_array,
    _parse_retry_after,
)


def _request_subjective_questions_from_groq(api_key, subject_name, chapter, class_level, num_questions, avoid_questions=None):
    """
    Asks Groq for a mix of CBSE board-exam-style subjective questions (short
    answer 2-3 markers and long answer 5-6 markers) for one chapter, each
    with a detailed model answer a student could use to self-check.

    avoid_questions: question texts already generated in a previous batch for
    this same chapter, so a multi-batch run (e.g. building up to 50 total)
    doesn't just repeat itself.
    """
    avoid_block = ""
    if avoid_questions:
        numbered = "\n".join(f"- {q}" for q in avoid_questions)
        avoid_block = (
            f"\n\nThese questions have ALREADY been used for this chapter - do NOT repeat them "
            f"or write close rewordings of them. Cover DIFFERENT sub-topics/angles instead:\n{numbered}\n"
        )

    prompt = f"""You are creating subjective (long-answer style) practice questions for Indian CBSE Class {class_level} {subject_name}, chapter: "{chapter}".

Write {num_questions} CBSE board-exam-style subjective questions covering the chapter, as a mix of:
- SHORT ANSWER questions worth 2-3 marks each (crisp, focused).
- LONG ANSWER questions worth 5-6 marks each (need a detailed, structured answer -
  multiple points, steps, or paragraphs as appropriate).

For each question, write a DETAILED model answer a Class {class_level} student could use to
self-check their own answer - matching the depth expected for that many marks.

Stay strictly within the depth of the official CBSE NCERT Class {class_level} syllabus for
this exact chapter - do not bring in concepts from a higher or lower class.
{avoid_block}
Respond with ONLY a JSON array, no other text, no markdown code fences. Format:
[
  {{
    "question": "question text here",
    "marks": 3,
    "answer": "detailed model answer, written as plain text (use \\n for line breaks between points/paragraphs)"
  }}
]

Return exactly {num_questions} questions."""

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "max_tokens": 8000,
            "reasoning_effort": "low",
        },
        timeout=90,
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
        questions = json.loads(text)
    except json.JSONDecodeError as e:
        questions = _try_salvage_json_array(text)
        if questions is None:
            raise MCQGenerationError(f"Could not parse subjective questions JSON: {e}\nRaw response:\n{text[:500]}")

    valid_questions = [
        q for q in questions
        if isinstance(q, dict) and q.get('question') and q.get('answer')
    ]

    if not valid_questions:
        raise MCQGenerationError("AI response had no valid, well-formed questions after filtering.")

    return valid_questions, response.headers


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def questions_to_pdf_sections(questions):
    """Maps [{'question','marks','answer'}] to the {'heading','content'} shape build_notes_pdf expects."""
    sections = []
    for i, q in enumerate(questions, start=1):
        marks = q.get('marks')
        marks_label = f" ({marks} marks)" if marks else ""
        sections.append({
            'heading': f"Q{i}. {q['question']}{marks_label}",
            'content': q['answer'],
        })
    return sections


def generate_subjective_questions_with_meta(api_key, subject_name, chapter, class_level, num_questions, avoid_questions=None):
    questions, headers = _request_subjective_questions_from_groq(
        api_key, subject_name, chapter, class_level, num_questions, avoid_questions
    )
    meta = {
        'remaining_tokens': _safe_int(headers.get('x-ratelimit-remaining-tokens')),
        'remaining_requests': _safe_int(headers.get('x-ratelimit-remaining-requests')),
    }
    return questions, meta


def generate_subjective_questions_with_rotation(api_keys, key_index, subject_name, chapter, class_level, num_questions, avoid_questions=None, on_rotate=None):
    """Same key-rotation pattern used elsewhere in the project."""
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            questions, meta = generate_subjective_questions_with_meta(
                api_keys[idx], subject_name, chapter, class_level, num_questions, avoid_questions
            )
            key_index[0] = idx
            return questions, meta
        except (RateLimitError, InvalidAPIKeyError) as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error


def generate_full_subjective_set(
    api_keys, key_index, subject_name, chapter, class_level,
    target_count=50, batch_size=15, max_batches=8, on_rotate=None, on_batch=None,
):
    """
    Builds up to `target_count` unique subjective questions for one chapter by
    calling Groq in smaller batches (safer than asking for 50 in one shot,
    which risks the response getting cut off mid-answer). Each batch is told
    which questions already exist so it covers new ground instead of
    repeating itself. Stops early if a batch adds nothing new twice in a row
    (AI has likely run out of distinct sub-topics), or after max_batches.

    on_batch(batch_num, collected_so_far), if given, is called after each
    batch - lets the caller log progress and sleep between batches.
    """
    collected = []
    seen_normalized = set()
    stale_batches = 0

    for batch_num in range(1, max_batches + 1):
        remaining = target_count - len(collected)
        if remaining <= 0:
            break
        this_batch_size = min(batch_size, remaining)

        avoid_list = [q['question'] for q in collected]
        try:
            questions, _meta = generate_subjective_questions_with_rotation(
                api_keys, key_index, subject_name, chapter, class_level,
                this_batch_size, avoid_questions=avoid_list or None, on_rotate=on_rotate,
            )
        except (RateLimitError, InvalidAPIKeyError, MCQGenerationError):
            # Whether it's exhausted keys or a parsing hiccup, stop here and
            # keep whatever we've already collected rather than losing it.
            break

        added = 0
        for q in questions:
            key = q['question'].strip().lower()
            if key not in seen_normalized:
                seen_normalized.add(key)
                collected.append(q)
                added += 1

        if on_batch:
            on_batch(batch_num, len(collected))

        stale_batches = stale_batches + 1 if added == 0 else 0
        if stale_batches >= 2:
            break

    return collected
