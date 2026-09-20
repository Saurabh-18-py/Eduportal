import re

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


def _strip_stray_markdown(text):
    """Safety net: the model is told not to use markdown, but if it slips up
    anyway, drop the ** / __ / # markers rather than showing them literally
    in the plain-text chat bubble. Left untouched: \\( \\) \\[ \\] (LaTeX)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    return text


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
    formatting = (
        "FORMATTING - this is a plain-text chat bubble, not a markdown renderer, so:\n"
        "- Never use markdown symbols: no **bold**, no *italics*, no # headings, no backticks, no markdown "
        "bullet dashes. If you emphasize a word, just write it plainly or in CAPS, don't wrap it in "
        "asterisks - literal ** characters will show up in the chat and look broken.\n"
        "- For maths, use LaTeX delimited with \\( ... \\) inline or \\[ ... \\] for a standalone line "
        "(this chat renders LaTeX), not markdown.\n"
        "- For step-by-step lists, use plain numbering on its own line: '1. ...', '2. ...' etc, one step "
        "per line - do not use markdown list syntax."
    )
    style = (
        "STYLE - answer the way full marks are awarded on a CBSE answer sheet, and nothing more:\n"
        "- For a numerical/derivation/proof question: write 'Given:' (only if the question supplies data), "
        "then numbered solution steps - each step is one short line of working, not a paragraph - then a "
        "final line starting 'Answer:' with the result. Skip steps a CBSE examiner wouldn't expect written "
        "out (don't re-derive standard formulas from scratch).\n"
        "- For a conceptual/theory question: 3-5 short numbered points covering exactly what's needed for "
        "full marks - definition/reason first, then supporting points, then a one-line example only if it "
        "genuinely clarifies. No extra background, no restating the question, no long intro sentence before "
        "you start answering.\n"
        "- Total reply length: aim for well under 150 words unless the question is a multi-part numerical "
        "that genuinely needs more steps. If you catch yourself writing a 4th paragraph, cut it down instead."
    )
    if class_level:
        return (
            f"You are a friendly, patient AI tutor on EduPortal, helping a CBSE Class {class_level} "
            f"student with their doubts, matching the depth of the official CBSE NCERT Class {class_level} "
            f"syllabus - don't casually bring in concepts from a higher class. If the question is "
            f"ambiguous, ask a brief clarifying question instead of guessing.\n\n{style}\n\n{formatting}"
            f"\n\n{guardrail}"
        )
    return (
        "You are a friendly, patient AI tutor on EduPortal, helping a CBSE school student with their "
        "doubts. If the question is ambiguous, ask a brief clarifying question instead of guessing.\n\n"
        f"{style}\n\n{formatting}\n\n{guardrail}"
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
    return _strip_stray_markdown(reply), response.headers


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
