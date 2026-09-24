import datetime

import requests
from django.utils import timezone

from .models import PageVisit, IPLocationCache

# Paths we never want to log - static/media assets, the admin panel itself,
# the dashboard itself (no point tracking visits to the analytics page),
# and health-check pings (e.g. UptimeRobot) which aren't real visitors.
IGNORED_PREFIXES = (
    '/static/', '/media/', '/admin/', '/analytics/', '/sw.js', '/favicon',
)

# How long a cached IP -> location lookup is considered fresh, before we
# bother re-checking it (IPs rarely move city, so this can be long).
CACHE_FRESH_DAYS = 30


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        # First entry is the original client, added by the edge proxy (Render).
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _lookup_location(ip_address):
    """
    Returns (country, city, lat, lon) for an IP, using a local cache first
    and falling back to the free ip-api.com endpoint (no key needed).
    Never raises - on any failure it just returns blanks, so a flaky
    geolocation lookup can never break the site.
    """
    if not ip_address or ip_address in ('127.0.0.1', 'localhost', '::1'):
        return '', '', None, None

    cutoff = timezone.now() - datetime.timedelta(days=CACHE_FRESH_DAYS)
    cached = IPLocationCache.objects.filter(ip_address=ip_address).first()
    if cached and cached.looked_up_at >= cutoff:
        return cached.country, cached.city, cached.latitude, cached.longitude

    country, city, lat, lon = '', '', None, None
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip_address}",
            params={'fields': 'status,country,city,lat,lon'},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                country = data.get('country', '') or ''
                city = data.get('city', '') or ''
                lat = data.get('lat')
                lon = data.get('lon')
    except Exception:
        pass  # geolocation is best-effort only

    if cached:
        cached.country, cached.city = country, city
        cached.latitude, cached.longitude = lat, lon
        cached.save(update_fields=['country', 'city', 'latitude', 'longitude', 'looked_up_at'])
    else:
        IPLocationCache.objects.create(
            ip_address=ip_address, country=country, city=city, latitude=lat, longitude=lon,
        )

    return country, city, lat, lon


class TrackVisitsMiddleware:
    """
    Logs every real page view to the database with an approximate
    (IP-based, no permission popup) location, for the owner-only analytics
    dashboard. Wrapped so tracking failures never break a page load.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            path = request.path
            if not path.startswith(IGNORED_PREFIXES) and response.status_code < 400:
                ip_address = _get_client_ip(request)
                country, city, lat, lon = _lookup_location(ip_address)
                PageVisit.objects.create(
                    path=path,
                    method=request.method,
                    ip_address=ip_address,
                    country=country,
                    city=city,
                    latitude=lat,
                    longitude=lon,
                    user=request.user if request.user.is_authenticated else None,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    referrer=request.META.get('HTTP_REFERER', '')[:500],
                )
        except Exception:
            pass  # tracking must never break the site

        return response
