import requests

from mocktest.ai_helpers import (
    GROQ_API_URL,
    GROQ_MODEL,
    RateLimitError,
    InvalidAPIKeyError,
    MCQGenerationError,
    _parse_retry_after,
)

MAX_HISTORY_MESSAGES = 12  # keep the last N messages (both roles) as context


def _system_prompt(class_level):
    guardrail = (
        "You ONLY help with academic doubts and questions from the student's CBSE school syllabus "
        "(any subject - Maths, Science, Social Science/History/Geography/Political Science/Economics/"
        "Sociology/Psychology, Accountancy, Business Studies, English, etc). You are NOT a general "
        "chatbot: politely decline anything that isn't a study doubt - casual chit-chat, personal "
        "questions, jokes, entertainment/movie/game recommendations, roleplay, or requests to write "
        "unrelated content (stories, poems, code for fun, etc). If a message isn't a syllabus doubt, "
        "reply briefly and kindly that you're only here to help with study doubts, and ask what topic "
        "they're stuck on - in ONE short sentence, don't lecture them."
    )
    if class_level:
        return (
            f"You are a friendly, patient AI tutor on EduPortal, helping a CBSE Class {class_level} "
            f"student with their doubts. Explain clearly and step by step, matching the depth of the "
            f"official CBSE NCERT Class {class_level} syllabus - don't casually bring in concepts from "
            f"a higher class. Use short paragraphs and a concrete example wherever it helps. If the "
            f"question is ambiguous, ask a brief clarifying question instead of guessing. Keep replies "
            f"focused - a few short paragraphs at most, not an essay.\n\n{guardrail}"
        )
    return (
        "You are a friendly, patient AI tutor on EduPortal, helping a CBSE school student with their "
        "doubts. Explain clearly and step by step. Use short paragraphs and a concrete example wherever "
        "it helps. If the question is ambiguous, ask a brief clarifying question instead of guessing. "
        f"Keep replies focused - a few short paragraphs at most, not an essay.\n\n{guardrail}"
    )


def _request_reply_from_groq(api_key, class_level, history):
    """
    history: list of {'role': 'user'|'assistant', 'content': str}, oldest
    first, ending with the student's latest message. Returns (reply_text, headers).
    """
    messages = [{"role": "system", "content": _system_prompt(class_level)}]
    messages.extend(history[-MAX_HISTORY_MESSAGES:])

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 1200,
            "reasoning_effort": "low",
        },
        timeout=45,
    )

    if response.status_code == 429:
        raise RateLimitError(f"Rate limited: {response.text}", _parse_retry_after(response.text))

    if response.status_code == 401:
        raise InvalidAPIKeyError(f"Invalid/revoked API key: {response.text}")

    if response.status_code != 200:
        raise MCQGenerationError(f"Groq API error ({response.status_code}): {response.text}")

    data = response.json()
    reply = data['choices'][0]['message']['content'].strip()
    if not reply:
        raise MCQGenerationError("AI returned an empty reply.")
    return reply, response.headers


def get_tutor_reply_with_rotation(api_keys, key_index, class_level, history, on_rotate=None):
    """Same key-rotation pattern used elsewhere in the project, adapted for a single quick chat reply."""
    n = len(api_keys)
    if n == 0:
        raise MCQGenerationError("No Groq API key configured (set GROQ_API_KEY or GROQ_API_KEYS).")

    last_error = None
    for attempt in range(n):
        idx = (key_index[0] + attempt) % n
        try:
            reply, _headers = _request_reply_from_groq(api_keys[idx], class_level, history)
            key_index[0] = idx
            return reply
        except (RateLimitError, InvalidAPIKeyError) as e:
            last_error = e
            if on_rotate:
                on_rotate(idx, (idx + 1) % n)
    raise last_error
