from django.contrib import admin

from .models import PushSubscription
from .push import send_push_to_subscription


@admin.action(description="Send a test push notification to selected devices")
def send_test_notification(modeladmin, request, queryset):
    sent, failed = 0, 0
    for sub in queryset:
        ok = send_push_to_subscription(
            sub,
            title="EduPortal",
            body="This is a test notification from the admin panel.",
        )
        if ok:
            sent += 1
        else:
            failed += 1
    modeladmin.message_user(request, f"Sent: {sent}, Failed: {failed}")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint_short', 'created_at')
    search_fields = ('user__username', 'endpoint')
    actions = [send_test_notification]

    def endpoint_short(self, obj):
        return obj.endpoint[:60] + ('...' if len(obj.endpoint) > 60 else '')
    endpoint_short.short_description = 'Endpoint'
