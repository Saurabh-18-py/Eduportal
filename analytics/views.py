import datetime

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .models import PageVisit


def _owner_only(user):
    return user.is_authenticated and user.is_superuser


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

    # map pins - one per distinct (lat, lon) with a visit count, most recent 30 days only
    pin_rows = (
        all_visits.filter(timestamp__gte=month_start)
        .exclude(latitude__isnull=True)
        .values('latitude', 'longitude', 'city', 'country')
        .annotate(views=Count('id'))
        .order_by('-views')
    )
    map_pins = list(pin_rows)

    context = {
        'total_visits': total_visits,
        'visits_today': visits_today,
        'visits_week': visits_week,
        'unique_visitors': unique_visitors,
        'top_pages': top_pages,
        'top_countries': top_countries,
        'top_cities': top_cities,
        'daily_labels': [d['label'] for d in daily_counts],
        'daily_values': [d['count'] for d in daily_counts],
        'map_pins': map_pins,
    }
    return render(request, 'analytics/dashboard.html', context)