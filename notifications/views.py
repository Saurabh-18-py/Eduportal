import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import PushSubscription
from .push import send_push_to_subscription


@login_required
@require_POST
def subscribe(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'bad_json'}, status=400)

    endpoint = data.get('endpoint')
    keys = data.get('keys') or {}
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not (endpoint and p256dh and auth):
        return JsonResponse({'ok': False, 'error': 'missing_fields'}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
        },
    )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def unsubscribe(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'bad_json'}, status=400)

    endpoint = data.get('endpoint')
    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()
    return JsonResponse({'ok': True})


def service_worker(request):
    """Served at /sw.js (root scope) — see notifications/static/sw.js."""
    with open(settings.BASE_DIR / 'notifications' / 'static_sw' / 'sw.js', 'rb') as f:
        content = f.read()
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response


@staff_member_required
def send_page(request):
    """A simple in-browser page (no shell / CLI needed) for staff to fire
    off a push notification — handy on Render's free tier, which doesn't
    include shell access."""
    results = None
    subscriber_count = PushSubscription.objects.count()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        url = request.POST.get('url', '/').strip() or '/'
        username = request.POST.get('username', '').strip()

        qs = PushSubscription.objects.all()
        if username:
            qs = qs.filter(user__username=username)

        sent, failed, errors = 0, 0, []
        if not title or not body:
            errors.append('Title and body are both required.')
        elif not qs.exists():
            errors.append('No matching subscriptions found.')
        else:
            for sub in qs:
                ok, error = send_push_to_subscription(sub, title, body, url)
                if ok:
                    sent += 1
                else:
                    failed += 1
                    errors.append(f'{sub.user.username}: {error}')

        results = {'sent': sent, 'failed': failed, 'errors': errors}

    return render(request, 'notifications/send.html', {
        'results': results,
        'subscriber_count': subscriber_count,
        'vapid_configured': bool(settings.VAPID_PRIVATE_KEY),
    })
