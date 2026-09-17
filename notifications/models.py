from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """One row per browser/device that has allowed push notifications.

    The endpoint + keys come straight from the browser's PushManager
    subscription object (see static/js/push.js). We store them so a
    server-side process (management command / admin action) can later
    send a push through pywebpush.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.endpoint[:40]}..."

    def as_subscription_info(self):
        """Shape pywebpush expects."""
        return {
            'endpoint': self.endpoint,
            'keys': {'p256dh': self.p256dh, 'auth': self.auth},
        }
