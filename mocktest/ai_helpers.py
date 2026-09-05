import json
import os
import re
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"


class MCQGenerationError(Exception):
    pass


class RateLimitError(MCQGenerationError):
    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = retry_after


def load_api_keys():
    """
    Loads one or more Groq API keys. Set GROQ_API_KEYS as a comma-separated
    list to rotate across multiple accounts once one hits its rate limit
    (e.g. "key_one,key_two"). Falls back to a single GROQ_API_KEY if that's
    all that's set.
    """
    multi = os.environ.get('GROQ_API_KEYS')
    if multi:
        return [k.strip() for k in multi.split(',') if k.strip()]
    single = os.environ.get('GROQ_API_KEY')
    return [single] if single else []


def _parse_retry_after(error_text):
    match = re.search(r'try again in ([\d.]+)s', error_text)
    if match:
        return float(match.group(1))
    return 20.0


def _try_salvage_json_array(text):
    """
    If the response got cut off mid-array (hit max_tokens), try to recover
    the questions that DID finish generating instead of throwing them all
    away: trim back to the last fully-closed '}' and re-close the array.
    """
    last_brace = text.rfind('}')
    if last_brace == -1:
        return None
    candidate = text[:last_brace + 1].rstrip()
    if candidate.endswith(','):
        candidate = candidate[:-1]
    if not candidate.startswith('['):
        return None
    candidate += ']'
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _request_mcqs_from_groq(api_key, subject_name, chapter, class_level, num_questions, difficulty):
    """
    Shared internals: calls Groq, parses the questions, and returns both the
    parsed questions AND the raw response headers (which carry Groq's
    rate-limit counters - used by the resumable top-up command to stop
    gracefully before hitting a hard 429).
    """
    difficulty_note = {
        'easy': "basic, direct recall questions",
        'medium': "standard CBSE board exam level questions",
        'hard': "tough, tricky, application/reasoning-based questions similar to HOTS (Higher Order Thinking Skills) questions",
    }[difficulty]

    prompt = f"""You are creating exam-style multiple choice practice questions for Indian CBSE Class {class_level} {subject_name}, chapter: "{chapter}".

Generate {num_questions} multiple choice questions in the style of previous-year CBSE board exam questions for this chapter. Make them {difficulty_note}. Each question must have exactly 4 DISTINCT options with exactly one correct answer. Keep each option short (avoid heavy LaTeX/markdown so the answer stays compact).

IMPORTANT - stay strictly within the depth of the official CBSE NCERT Class {class_level} syllabus for this exact chapter. "Hard" means tricky and thought-provoking WITHIN that grade's syllabus (e.g. multi-step reasoning, common misconceptions, applying a concept in a new context) - it does NOT mean borrowing concepts, formulas, or terminology from a higher class. For example, in Class 9-10 Acids/Bases/Salts, do NOT bring in titration equivalence-point calculations, conjugate acid-base pairs, or ionic equilibrium - those belong to Class 11-12 and would be out of syllabus here.

Respond with ONLY a JSON array, no other text, no markdown code fences, no explanation. Format:
[
  {{
    "question": "question text here",
    "options": ["option A", "option B", "option C", "option D"],
    "correct_answer": "the exact text of the correct option"
  }}
]"""

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8000,
            # GPT-OSS models default to "medium" reasoning effort, which can
            # burn most of max_tokens on hidden reasoning before ever writing
            # the JSON answer, causing truncated/empty responses. "low" keeps
            # far more of the token budget for the actual output.
            "reasoning_effort": "low",
        },
        timeout=60,
    )

    if response.status_code == 429:
        retry_after = _parse_retry_after(response.text)
        raise RateLimitError(f"Rate limited: {response.text}", retry_after)

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
            raise MCQGenerationError(f"Could not parse AI response as JSON: {e}\nRaw response:\n{text[:500]}")

    valid_questions = []
    for q in questions:
        opts = q.get('options', [])
        if (
            isinstance(opts, list)
            and len(opts) == 4
            and len(set(opts)) == 4  # all 4 options must be genuinely distinct
            and q.get('correct_answer') in opts
        ):
            valid_questions.append(q)

    if not valid_questions:
        raise MCQGenerationError("AI response had no valid, well-formed questions after filtering.")

    return valid_questions, response.headers


def generate_mcqs_via_groq(api_key, subject_name, chapter, class_level, num_questions, difficulty):
    questions, _headers = _request_mcqs_from_groq(
        api_key, subject_name, chapter, class_level, num_questions, difficulty
    )
    return questions


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def generate_mcqs_batch_with_meta(api_key, subject_name, chapter, class_level, num_questions, difficulty):
    """
    Same as generate_mcqs_via_groq, but also returns how many tokens/requests
    Groq says are left for today, so a long-running batch job can stop itself
    cleanly instead of crashing into a 429.
    """
    questions, headers = _request_mcqs_from_groq(
        api_key, subject_name, chapter, class_level, num_questions, difficulty
    )
    meta = {
        'remaining_tokens': _safe_int(headers.get('x-ratelimit-remaining-tokens')),
        'remaining_requests': _safe_int(headers.get('x-ratelimit-remaining-requests')),
    }
    return questions, meta


def generate_mcqs_batch_with_rotation(api_keys, key_index, subject_name, chapter, class_level, num_questions, difficulty, on_rotate=None):
    """
    Like generate_mcqs_batch_with_meta, but tries multiple API keys: starts
    from api_keys[key_index[0]] and, on a RateLimitError, rotates to the next
    key and retries the SAME request, until one succeeds or every key has
    been tried. key_index is a single-item list used as a shared "cursor" so
    later calls resume from whichever key last worked (instead of resetting
    to key 0 and re-triggering its rate limit every time).

    on_rotate(old_index, new_index), if given, is called whenever a key gets
    skipped, so the caller can log it. Raises the last RateLimitError only
    once every key has failed.
    """
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            questions, meta = generate_mcqs_batch_with_meta(
                api_keys[idx], subject_name, chapter, class_level, num_questions, difficulty
            )
            key_index[0] = idx
            return questions, meta
        except RateLimitError as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error


def _request_audit_from_groq(api_key, subject_name, chapter, class_level, questions):
    """
    Asks Groq to judge, for each question TEXT (options aren't needed for
    this and would just cost extra tokens), whether it fits the Class
    {class_level} syllabus depth for this chapter or actually leaks in
    concepts from a higher class. This is classification, not generation -
    much cheaper per call than writing new questions.

    Returns (results, headers) where results is a list of
    {'in_syllabus': bool, 'reason': str}, same order/length as `questions`.
    """
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))

    prompt = f"""You are checking whether practice questions match the depth of the official CBSE NCERT Class {class_level} syllabus for {subject_name}, chapter "{chapter}".

For EACH question below, decide if it fits within Class {class_level}'s syllabus depth for this chapter, or if it actually requires concepts/formulas/terminology that only appear in a HIGHER class (e.g. a Class 9-10 question using Class 11-12 ideas like titration equivalence points, conjugate acid-base pairs, calculus, or biology terms like operon/codon/Krebs cycle).

Questions:
{numbered}

Respond with ONLY a JSON array of exactly {len(questions)} objects, in the same order as the questions, no other text, no markdown fences:
[
  {{"in_syllabus": true, "reason": ""}},
  {{"in_syllabus": false, "reason": "short reason why it's out of syllabus"}}
]"""

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4000,
            "reasoning_effort": "low",
        },
        timeout=60,
    )

    if response.status_code == 429:
        retry_after = _parse_retry_after(response.text)
        raise RateLimitError(f"Rate limited: {response.text}", retry_after)

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
        results = json.loads(text)
    except json.JSONDecodeError as e:
        results = _try_salvage_json_array(text)
        if results is None:
            raise MCQGenerationError(f"Could not parse audit response as JSON: {e}\nRaw response:\n{text[:500]}")

    # Defensive normalization: if the AI returned fewer/malformed entries,
    # default the missing ones to "keep" (in_syllabus=True) rather than
    # risk auto-deleting a perfectly fine question due to a parsing hiccup.
    normalized = []
    for i in range(len(questions)):
        entry = results[i] if i < len(results) else None
        if isinstance(entry, dict) and 'in_syllabus' in entry:
            normalized.append({
                'in_syllabus': bool(entry['in_syllabus']),
                'reason': entry.get('reason', ''),
            })
        else:
            normalized.append({'in_syllabus': True, 'reason': '(unparsed - kept by default)'})

    return normalized, response.headers


def audit_questions_batch_with_meta(api_key, subject_name, chapter, class_level, questions):
    results, headers = _request_audit_from_groq(api_key, subject_name, chapter, class_level, questions)
    meta = {
        'remaining_tokens': _safe_int(headers.get('x-ratelimit-remaining-tokens')),
        'remaining_requests': _safe_int(headers.get('x-ratelimit-remaining-requests')),
    }
    return results, meta


def audit_questions_batch_with_rotation(api_keys, key_index, subject_name, chapter, class_level, questions, on_rotate=None):
    """Same key-rotation pattern as generate_mcqs_batch_with_rotation, but for the audit call."""
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            results, meta = audit_questions_batch_with_meta(
                api_keys[idx], subject_name, chapter, class_level, questions
            )
            key_index[0] = idx
            return results, meta
        except RateLimitError as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error
