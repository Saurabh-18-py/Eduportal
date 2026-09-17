import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mocktest.ai_helpers import load_api_keys, MCQGenerationError
from .doubt_ai import get_tutor_reply_with_rotation
from .models import DoubtMessage

DEFAULT_DAILY_LIMIT = 10

# Module-level cursor shared across requests in this process, so repeated
# doubts don't keep re-triggering the same exhausted key's rate limit.
_key_index = [0]


@login_required
def doubt_chat(request):
    history = DoubtMessage.objects.filter(student=request.user).order_by('created_at')
    limit = getattr(getattr(request.user, 'profile', None), 'doubt_limit_per_day', DEFAULT_DAILY_LIMIT)
    asked_today = DoubtMessage.objects.filter(
        student=request.user, role='user', created_at__date=timezone.localdate()
    ).count()
    return render(request, 'doubtsolver/chat.html', {
        'history': history,
        'doubts_left': max(limit - asked_today, 0),
        'doubt_limit': limit,
    })


@login_required
@require_POST
def ask_doubt(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': "Couldn't read that message, try again."}, status=400)

    question = (payload.get('message') or '').strip()
    if not question:
        return JsonResponse({'error': 'Type a doubt first.'}, status=400)
    if len(question) > 2000:
        return JsonResponse({'error': "That's a bit long - try breaking it into smaller doubts."}, status=400)

    limit = getattr(getattr(request.user, 'profile', None), 'doubt_limit_per_day', DEFAULT_DAILY_LIMIT)
    asked_today = DoubtMessage.objects.filter(
        student=request.user, role='user', created_at__date=timezone.localdate()
    ).count()
    if asked_today >= limit:
        return JsonResponse({
            'error': (
                f"You've used all {limit} doubts for today. It resets at midnight - "
                f"or message Saurabh (Message option in the menu) if you need more."
            ),
            'limit_reached': True,
        }, status=429)

    DoubtMessage.objects.create(student=request.user, role='user', content=question)

    recent = DoubtMessage.objects.filter(student=request.user).order_by('-created_at')[:12]
    history = [{'role': m.role, 'content': m.content} for m in reversed(recent)]

    api_keys = load_api_keys()
    class_level = getattr(getattr(request.user, 'profile', None), 'class_level', None)

    try:
        reply = get_tutor_reply_with_rotation(api_keys, _key_index, class_level, history)
    except MCQGenerationError:
        reply = (
            "Sorry, I couldn't reach the AI tutor just now (it might be busy). "
            "Please try again in a moment."
        )

    DoubtMessage.objects.create(student=request.user, role='assistant', content=reply)

    return JsonResponse({'reply': reply})
