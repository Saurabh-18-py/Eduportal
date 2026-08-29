import json
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


def _parse_retry_after(error_text):
    match = re.search(r'try again in ([\d.]+)s', error_text)
    if match:
        return float(match.group(1))
    return 20.0


def generate_mcqs_via_groq(api_key, subject_name, chapter, class_level, num_questions, difficulty):
    difficulty_note = {
        'easy': "basic, direct recall questions",
        'medium': "standard CBSE board exam level questions",
        'hard': "tough, tricky, application/reasoning-based questions similar to HOTS (Higher Order Thinking Skills) questions",
    }[difficulty]

    prompt = f"""You are creating exam-style multiple choice practice questions for Indian CBSE Class {class_level} {subject_name}, chapter: "{chapter}".

Generate {num_questions} multiple choice questions in the style of previous-year CBSE board exam questions for this chapter. Make them {difficulty_note}. Each question must have exactly 4 options with exactly one correct answer.

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
            "max_tokens": 7500,
        },
        timeout=60,
    )

    if response.status_code == 429:
        retry_after = _parse_retry_after(response.text)
        raise RateLimitError(f"Rate limited: {response.text}", retry_after)

    if response.status_code != 200:
        raise MCQGenerationError(f"Groq API error ({response.status_code}): {response.text}")

    data = response.json()
    message = data['choices'][0]['message']
    text = (message.get('content') or '').strip()

    if not text:
        finish_reason = data['choices'][0].get('finish_reason', 'unknown')
        raise MCQGenerationError(
            f"AI returned an empty response (finish_reason: {finish_reason}). "
            f"This usually means the model ran out of tokens while reasoning. Try again."
        )

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        questions = json.loads(text)
    except json.JSONDecodeError as e:
        raise MCQGenerationError(f"Could not parse AI response as JSON: {e}\nRaw response:\n{text[:500]}")

    for q in questions:
        if len(q.get('options', [])) != 4 or q.get('correct_answer') not in q.get('options', []):
            raise MCQGenerationError(f"Malformed question from AI: {q}")

    return questions
