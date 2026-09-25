from django.conf import settings
from django.db import models


class IPLocationCache(models.Model):
    """
    Caches IP -> location lookups so we don't hit the free geolocation API
    for every single request from the same visitor (free tier is rate
    limited to ~45 requests/minute).
    """
    ip_address = models.GenericIPAddressField(unique=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    looked_up_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ip_address} -> {self.city}, {self.country}"


class PageVisit(models.Model):
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, default='GET')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_verified = models.BooleanField(
        default=False,
        help_text="True if this location came from the visitor's own device GPS "
                   "(they tapped 'Allow'), not just guessed from their IP address.",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    user_agent = models.CharField(max_length=500, blank=True)
    referrer = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['country']),
            models.Index(fields=['path']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f"{self.path} @ {self.timestamp:%Y-%m-%d %H:%M} ({self.city or 'unknown'})"
