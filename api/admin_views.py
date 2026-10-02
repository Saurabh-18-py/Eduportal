import os

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Message
from notes.models import Chapter, Note, PYQPaper, Subject
from notifications.models import ExpoPushToken

from .expo_push import send_expo_push

MAX_PDF_MB = 40


class IsSuperuser(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_superuser)


class RegisterPushTokenView(APIView):
    """POST /api/push/register/ {"token": "ExponentPushToken[...]"}"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = str(request.data.get('token', '')).strip()
        if not token.startswith(('ExponentPushToken[', 'ExpoPushToken[')):
            return Response({'error': 'Invalid push token.'}, status=status.HTTP_400_BAD_REQUEST)
        ExpoPushToken.objects.update_or_create(token=token, defaults={'user': request.user})
        return Response({'ok': True})


class UnregisterPushTokenView(APIView):
    """POST /api/push/unregister/ {"token": "..."} - called on logout."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = str(request.data.get('token', '')).strip()
        if token:
            ExpoPushToken.objects.filter(token=token, user=request.user).delete()
        return Response({'ok': True})


class NotifyView(APIView):
    """
    POST /api/admin/notify/
    {"title": "...", "body": "...", "target": "all" | "user", "username": "...", "also_in_app": true}
    """
    permission_classes = [IsSuperuser]

    def post(self, request):
        title = str(request.data.get('title', '')).strip()[:100]
        body = str(request.data.get('body', '')).strip()[:500]
        if not title or not body:
            return Response({'error': 'Title and message are both required.'}, status=400)

        target = request.data.get('target', 'all')
        users = User.objects.filter(is_active=True)
        if target == 'user':
            username = str(request.data.get('username', '')).strip()
            if not username:
                return Response({'error': 'Enter the username.'}, status=400)
            users = users.filter(username__iexact=username)
            if not users.exists():
                return Response({'error': 'No user with that username.'}, status=404)

        also_in_app = request.data.get('also_in_app', True)
        if isinstance(also_in_app, str):
            also_in_app = also_in_app.lower() in ('1', 'true', 'yes')

        tokens = list(ExpoPushToken.objects.filter(user__in=users).values_list('token', flat=True))
        sent, failed, dead = send_expo_push(tokens, title, body)
        if dead:
            ExpoPushToken.objects.filter(token__in=dead).delete()

        in_app = 0
        if also_in_app:
            students = list(users.filter(profile__isnull=False).exclude(id=request.user.id))
            text = f"{title}\n\n{body}"
            Message.objects.bulk_create(
                [Message(sender=request.user, recipient=u, text=text) for u in students]
            )
            in_app = len(students)

        return Response({'devices': len(tokens), 'sent': sent, 'failed': failed, 'in_app': in_app})


def _check_pdf(f):
    if not f:
        return 'Choose a PDF file.'
    if not f.name.lower().endswith('.pdf'):
        return 'Only PDF files are allowed.'
    if f.size > MAX_PDF_MB * 1024 * 1024:
        return f'File is too big (max {MAX_PDF_MB} MB).'
    return None


def _title_from_filename(name):
    base = os.path.splitext(name)[0].replace('_', ' ').replace('-', ' ').strip()
    return base or name


class UploadNoteView(APIView):
    """POST /api/admin/upload/note/  multipart: chapter, title (optional), resource_type, file"""
    permission_classes = [IsSuperuser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get('file')
        err = _check_pdf(f)
        if err:
            return Response({'error': err}, status=400)
        try:
            chapter = Chapter.objects.get(id=int(request.data.get('chapter')))
        except (TypeError, ValueError, Chapter.DoesNotExist):
            return Response({'error': 'Choose a valid chapter.'}, status=400)
        resource_type = request.data.get('resource_type', 'notes')
        if resource_type not in ('notes', 'subjective'):
            return Response({'error': 'Type must be notes or subjective.'}, status=400)
        title = str(request.data.get('title', '')).strip()[:200] or _title_from_filename(f.name)[:200]

        note = Note.objects.create(chapter=chapter, title=title, resource_type=resource_type, pdf_file=f)
        cache.delete(f'chapters:subject:{chapter.subject_id}')
        return Response(
            {'id': note.id, 'title': note.title, 'resource_type': note.resource_type},
            status=status.HTTP_201_CREATED,
        )


class UploadPYQView(APIView):
    """POST /api/admin/upload/pyq/  multipart: subject, year, set_label (optional), file"""
    permission_classes = [IsSuperuser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get('file')
        err = _check_pdf(f)
        if err:
            return Response({'error': err}, status=400)
        try:
            subject = Subject.objects.get(id=int(request.data.get('subject')))
        except (TypeError, ValueError, Subject.DoesNotExist):
            return Response({'error': 'Choose a valid subject.'}, status=400)
        try:
            year = int(request.data.get('year'))
            if not 1990 <= year <= 2100:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'error': 'Enter a valid year, e.g. 2024.'}, status=400)
        set_label = str(request.data.get('set_label', '')).strip()[:50]

        paper = PYQPaper.objects.create(
            subject=subject, class_level=subject.class_level, year=year, set_label=set_label, pdf_file=f
        )
        return Response({'id': paper.id, 'year': paper.year}, status=status.HTTP_201_CREATED)
