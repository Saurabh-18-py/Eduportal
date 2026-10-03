from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile
from doubtsolver.models import DoubtMessage
from mocktest.models import Question, TestAttempt
from notes.models import Note, PYQPaper
from notifications.models import ExpoPushToken

from .admin_views import IsSuperuser

PAGE_SIZE = 30


def summarize_attempts(rows):
    """rows: (student_id, score, total, submitted_at) -> {student_id: (count, avg_pct, last)}"""
    acc = defaultdict(lambda: [0, 0.0, None])
    for sid, score, total, when in rows:
        a = acc[sid]
        a[0] += 1
        if total:
            a[1] += score * 100.0 / total
        if when and (a[2] is None or when > a[2]):
            a[2] = when
    return {sid: (n, round(s / n) if n else None, last) for sid, (n, s, last) in acc.items()}


class OverviewView(APIView):
    """GET /api/admin/overview/ - headline numbers for the admin dashboard."""
    permission_classes = [IsSuperuser]

    def get(self, request):
        week = timezone.now() - timedelta(days=7)
        students = StudentProfile.objects.all()
        done = TestAttempt.objects.filter(submitted_at__isnull=False)
        return Response({
            'students': students.count(),
            'students_by_class': {str(c): students.filter(class_level=c).count() for c in (9, 10, 11, 12)},
            'new_students_7d': students.filter(created_at__gte=week).count(),
            'attempts_total': done.count(),
            'attempts_7d': done.filter(submitted_at__gte=week).count(),
            'active_students_7d': done.filter(submitted_at__gte=week).values('student').distinct().count(),
            'doubts_7d': DoubtMessage.objects.filter(role='user', created_at__gte=week).count(),
            'notes': Note.objects.count(),
            'pyq': PYQPaper.objects.count(),
            'questions': Question.objects.count(),
            'push_devices': ExpoPushToken.objects.count(),
        })


class UserListView(APIView):
    """GET /api/admin/users/?q=&class_level=&page="""
    permission_classes = [IsSuperuser]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        qs = StudentProfile.objects.select_related('user')
        if q:
            qs = qs.filter(
                Q(user__username__icontains=q) | Q(user__email__icontains=q) | Q(phone__icontains=q)
            )
        cl = request.query_params.get('class_level')
        if cl and cl.isdigit():
            qs = qs.filter(class_level=int(cl))
        qs = qs.order_by('-created_at')

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except ValueError:
            page = 1
        total = qs.count()
        profiles = list(qs[(page - 1) * PAGE_SIZE: page * PAGE_SIZE])

        ids = [p.user_id for p in profiles]
        stats = summarize_attempts(
            TestAttempt.objects.filter(student_id__in=ids, submitted_at__isnull=False)
            .values_list('student_id', 'score', 'total', 'submitted_at')
        )
        results = []
        for p in profiles:
            n, avg, last = stats.get(p.user_id, (0, None, None))
            results.append({
                'id': p.user_id,
                'username': p.user.username,
                'email': p.user.email,
                'class_level': p.class_level,
                'phone': p.phone,
                'joined': p.created_at,
                'last_login': p.user.last_login,
                'attempts': n,
                'avg': avg,
                'last_attempt': last,
                'is_active': p.user.is_active,
            })
        return Response({'total': total, 'page': page, 'page_size': PAGE_SIZE, 'results': results})


class UserDetailView(APIView):
    """GET /api/admin/users/<id>/ and PATCH {"doubt_limit_per_day": 20, "is_active": true}"""
    permission_classes = [IsSuperuser]

    def _payload(self, user):
        profile = StudentProfile.objects.filter(user=user).first()
        attempts = list(
            TestAttempt.objects.filter(student=user, submitted_at__isnull=False)
            .select_related('test', 'test__subject').order_by('-submitted_at')[:15]
        )
        today = timezone.localdate()
        asked_today = DoubtMessage.objects.filter(student=user, role='user', created_at__date=today).count()
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_admin': user.is_superuser,
            'joined': profile.created_at if profile else user.date_joined,
            'last_login': user.last_login,
            'class_level': profile.class_level if profile else None,
            'phone': profile.phone if profile else '',
            'doubt_limit': profile.doubt_limit_per_day if profile else None,
            'doubts_today': asked_today,
            'doubts_total': DoubtMessage.objects.filter(student=user, role='user').count(),
            'devices': ExpoPushToken.objects.filter(user=user).count(),
            'attempts': [
                {
                    'id': a.id,
                    'title': a.test.title.replace(' - Practice Test', ''),
                    'subject': a.test.subject.name,
                    'slice': a.slice_number,
                    'score': a.score,
                    'total': a.total,
                    'seconds': a.duration_seconds,
                    'when': a.submitted_at,
                }
                for a in attempts
            ],
        }

    def get(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        return Response(self._payload(user))

    def patch(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)

        if 'doubt_limit_per_day' in request.data:
            profile = StudentProfile.objects.filter(user=user).first()
            if not profile:
                return Response({'error': 'This user has no student profile.'}, status=400)
            try:
                limit = int(request.data['doubt_limit_per_day'])
                if not 0 <= limit <= 500:
                    raise ValueError
            except (TypeError, ValueError):
                return Response({'error': 'Doubt limit must be a number from 0 to 500.'}, status=400)
            profile.doubt_limit_per_day = limit
            profile.save(update_fields=['doubt_limit_per_day'])

        if 'is_active' in request.data:
            if user.id == request.user.id:
                return Response({'error': "You can't deactivate your own account."}, status=400)
            value = request.data['is_active']
            if isinstance(value, str):
                value = value.lower() in ('1', 'true', 'yes')
            user.is_active = bool(value)
            user.save(update_fields=['is_active'])

        return Response(self._payload(user))
