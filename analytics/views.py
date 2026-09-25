import datetime
import json

import requests
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .models import PageVisit


def _owner_only(user):
    return user.is_authenticated and user.is_superuser


def _reverse_geocode(lat, lon):
    """
    Best-effort reverse geocoding using OpenStreetMap's free Nominatim
    service. Returns (country, city) - blanks on any failure, since this
    is a nice-to-have and must never break the request.
    """
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={'lat': lat, 'lon': lon, 'format': 'json', 'zoom': 10},
            headers={'User-Agent': 'EduPortal-Analytics/1.0'},
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            address = data.get('address', {})
            city = (
                address.get('city') or address.get('town')
                or address.get('village') or address.get('county') or ''
            )
            country = address.get('country', '')
            return country, city
    except Exception:
        pass
    return '', ''


@csrf_exempt
@require_POST
def report_location(request):
    """
    Called from the browser (only if the visitor tapped 'Allow' on our
    optional location banner) with their precise GPS coordinates. Updates
    their most recent visit this session with accurate location data.
    Silently no-ops on any problem - this is purely a nice-to-have.
    """
    try:
        data = json.loads(request.body)
        lat = float(data['latitude'])
        lon = float(data['longitude'])
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    session_key = request.session.session_key
    if not session_key:
        return JsonResponse({'ok': False}, status=400)

    country, city = _reverse_geocode(lat, lon)

    visit = PageVisit.objects.filter(session_key=session_key).order_by('-timestamp').first()
    if visit:
        visit.latitude = lat
        visit.longitude = lon
        if country:
            visit.country = country
        if city:
            visit.city = city
        visit.location_verified = True
        visit.save(update_fields=['latitude', 'longitude', 'country', 'city', 'location_verified'])

    return JsonResponse({'ok': True})


@user_passes_test(_owner_only)
def dashboard(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=7)
    month_start = today_start - datetime.timedelta(days=30)

    all_visits = PageVisit.objects.all()

    total_visits = all_visits.count()
    visits_today = all_visits.filter(timestamp__gte=today_start).count()
    visits_week = all_visits.filter(timestamp__gte=week_start).count()
    unique_visitors = all_visits.exclude(ip_address__isnull=True).values('ip_address').distinct().count()
    verified_count = all_visits.filter(location_verified=True).count()

    top_pages = (
        all_visits.values('path')
        .annotate(views=Count('id'))
        .order_by('-views')[:10]
    )
    top_countries = (
        all_visits.exclude(country='')
        .values('country')
        .annotate(views=Count('id'))
        .order_by('-views')[:10]
    )
    top_cities = (
        all_visits.exclude(city='')
        .values('city', 'country')
        .annotate(views=Count('id'))
        .order_by('-views')[:10]
    )

    # last 14 days, visits per day - for the trend chart
    daily_counts = []
    for i in range(13, -1, -1):
        day_start = today_start - datetime.timedelta(days=i)
        day_end = day_start + datetime.timedelta(days=1)
        count = all_visits.filter(timestamp__gte=day_start, timestamp__lt=day_end).count()
        daily_counts.append({'label': day_start.strftime('%d %b'), 'count': count})

    recent_visits = (
        all_visits.select_related('user')[:30]
    )

    context = {
        'total_visits': total_visits,
        'visits_today': visits_today,
        'visits_week': visits_week,
        'unique_visitors': unique_visitors,
        'verified_count': verified_count,
        'top_pages': top_pages,
        'top_countries': top_countries,
        'top_cities': top_cities,
        'daily_labels': [d['label'] for d in daily_counts],
        'daily_values': [d['count'] for d in daily_counts],
        'recent_visits': recent_visits,
    }
    return render(request, 'analytics/dashboard.html', context)