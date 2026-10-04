from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile
from mocktest.models import TestAttempt

IST = ZoneInfo('Asia/Kolkata')
GOALS = (10, 20, 30, 50)


def compute_streak(day_totals, goal, today):
    """day_totals: {date: questions answered that day}. A day counts when it reaches the goal."""
    met = {d for d, n in day_totals.items() if n >= goal}

    current = 0
    d = today if today in met else today - timedelta(days=1)
    while d in met:
        current += 1
        d -= timedelta(days=1)

    best = 0
    for d in met:
        if d - timedelta(days=1) not in met:
            run, e = 1, d
            while e + timedelta(days=1) in met:
                run += 1
                e += timedelta(days=1)
            best = max(best, run)

    week = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        week.append({'date': day.isoformat(), 'count': day_totals.get(day, 0), 'met': day in met})

    return {
        'streak': current,
        'best': best,
        'today': day_totals.get(today, 0),
        'week': week,
        'active_days': sum(1 for n in day_totals.values() if n > 0),
    }


def _payload(user, goal):
    rows = TestAttempt.objects.filter(student=user, submitted_at__isnull=False).values_list('submitted_at', 'total')
    totals = {}
    for when, total in rows:
        day = when.astimezone(IST).date()
        totals[day] = totals.get(day, 0) + (total or 0)
    today = datetime.now(IST).date()
    return {'goal': goal, 'goals': list(GOALS), **compute_streak(totals, goal, today)}


class StreakView(APIView):
    """GET /api/streak/ and PATCH /api/streak/ {"goal": 20}"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = StudentProfile.objects.filter(user=request.user).first()
        return Response(_payload(request.user, profile.daily_goal if profile else 10))

    def patch(self, request):
        profile = StudentProfile.objects.filter(user=request.user).first()
        if not profile:
            return Response({'error': 'No student profile.'}, status=400)
        try:
            goal = int(request.data.get('goal'))
        except (TypeError, ValueError):
            goal = 0
        if goal not in GOALS:
            return Response({'error': 'Choose 10, 20, 30 or 50 questions.'}, status=400)
        profile.daily_goal = goal
        profile.save(update_fields=['daily_goal'])
        return Response(_payload(request.user, goal))
