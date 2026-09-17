import json

from django.conf import settings


def send_push_to_subscription(subscription, title, body, url='/'):
    """Send one push notification. Returns (True, None) on success or
    (False, error_message) on failure.

    Deletes the subscription automatically if the browser reports it as
    expired/gone (HTTP 404/410) so we don't keep retrying dead endpoints.
    """
    if not settings.VAPID_PRIVATE_KEY:
        return False, 'VAPID_PRIVATE_KEY is not set in the environment.'

    from pywebpush import webpush, WebPushException

    payload = json.dumps({'title': title, 'body': body, 'url': url})

    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={**settings.VAPID_CLAIMS},
        )
        return True, None
    except WebPushException as exc:
        status = getattr(exc.response, 'status_code', None)
        detail = str(exc)
        if getattr(exc, 'response', None) is not None:
            try:
                detail = f"{status} {exc.response.text}"
            except Exception:
                pass
        if status in (404, 410):
            subscription.delete()
        return False, detail
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'
