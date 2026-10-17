import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AdminProfile, StudentProfile
from mocktest.models import Question, Test
from notes.models import Note

MAX_VIDEO_BYTES = 60 * 1024 * 1024  # 60 MB
VIDEO_EXTS = ('.mp4', '.mov', '.webm', '.mkv', '.m4v', '.3gp')
YT_RE = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})')


class IsSuperuser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def _owner():
    return get_user_model().objects.filter(is_superuser=True).order_by('id').first()


def _video_info(ap, request):
    if not ap:
        return None
    if ap.video_link:
        m = YT_RE.search(ap.video_link)
        if m:
            return {'kind': 'youtube', 'url': ap.video_link, 'youtube_id': m.group(1)}
        return {'kind': 'link', 'url': ap.video_link, 'youtube_id': None}
    if ap.video:
        url = ap.video.url
        return {'kind': 'file', 'url': request.build_absolute_uri(url) if url.startswith('/') else url, 'youtube_id': None}
    return None


def avatar_video_url(request):
    """Small square video for the admin's round avatar in Messages (None if there is no playable video)."""
    admin = _owner()
    ap = getattr(admin, 'admin_profile', None) if admin else None
    info = _video_info(ap, request)
    if not info or info['kind'] == 'youtube':
        return None
    url = info['url']
    if '/video/upload/' in url:
        # Cloudinary: tiny 200x200 clip, first 8 seconds, light quality -> loads fast and loops nicely
        url = url.replace('/video/upload/', '/video/upload/w_200,h_200,c_fill,du_8,q_auto:low,f_mp4/', 1)
        return re.sub(r'\.[A-Za-z0-9]{2,4}(\?.*)?$', '.mp4', url)
    if info['kind'] == 'link' and not re.search(r'\.(mp4|webm|mov|m4v)(\?|#|$)', url, re.I):
        return None
    return url


class AdminProfileView(APIView):
    """GET /api/admin-profile/ - the site owner's public profile (opens when someone taps the admin photo in Messages)."""
    permission_classes = [permissions.IsAuthenticated]

    # ---- Edit these texts any time ----
    DISPLAY_NAME = 'Saurabh'
    TITLE = 'Founder & Developer, EduPortal'
    BIO = (
        "Hi, I'm Saurabh. I build and run EduPortal on my own, so every note, mock test "
        "and fix you see here comes straight from me. My goal is simple: good chapter-wise "
        "CBSE practice for every student, right on your phone."
    )
    HIGHLIGHTS = [
        'Chapter-wise notes and mock tests for CBSE Class 9-12',
        'AI doubt solver for quick help',
        'Message me with feedback or any problem you face',
    ]

    def get(self, request):
        admin = _owner()
        ap = getattr(admin, 'admin_profile', None) if admin else None
        avatar_url = request.build_absolute_uri(ap.image.url) if ap and ap.image else None

        stats = cache.get('admin_profile_stats')
        if stats is None:
            stats = {
                'students': StudentProfile.objects.count(),
                'notes': Note.objects.count(),
                'tests': Test.objects.count(),
                'questions': Question.objects.count(),
            }
            cache.set('admin_profile_stats', stats, 600)

        return Response({
            'name': (admin.first_name if admin and admin.first_name else self.DISPLAY_NAME),
            'title': self.TITLE,
            'bio': self.BIO,
            'avatar_url': avatar_url,
            'highlights': self.HIGHLIGHTS,
            'stats': stats,
            'video': _video_info(ap, request),
            'can_edit': bool(request.user.is_superuser),
        })


class AdminProfileVideoView(APIView):
    """
    POST   /api/admin/profile-video/   multipart 'file'  OR  {"link": "https://..."}  -> set the profile video
    DELETE /api/admin/profile-video/                                              -> remove it
    """
    permission_classes = [IsSuperuser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @staticmethod
    def _drop_file(ap):
        try:
            if ap.video:
                ap.video.delete(save=False)
        except Exception:
            pass

    def post(self, request):
        ap, _ = AdminProfile.objects.get_or_create(user=request.user)
        link = str(request.data.get('link', '') or '').strip()
        f = request.FILES.get('file')

        if link:
            if not re.match(r'^https?://\S+$', link):
                return Response({'error': 'Enter a valid link starting with http:// or https://'}, status=400)
            self._drop_file(ap)
            ap.video = None
            ap.video_link = link[:500]
        elif f:
            ctype = (getattr(f, 'content_type', '') or '').lower()
            if not (ctype.startswith('video/') or f.name.lower().endswith(VIDEO_EXTS)):
                return Response({'error': 'Please choose a video file.'}, status=400)
            if f.size > MAX_VIDEO_BYTES:
                return Response({'error': 'Video is too big (max 60 MB). Paste a YouTube link instead.'}, status=400)
            self._drop_file(ap)
            ap.video = f
            ap.video_link = ''
        else:
            return Response({'error': 'Send a video file or a link.'}, status=400)

        ap.save()
        return Response({'video': _video_info(ap, request)})

    def delete(self, request):
        ap = AdminProfile.objects.filter(user=request.user).first()
        if ap:
            self._drop_file(ap)
            ap.video = None
            ap.video_link = ''
            ap.save()
        return Response({'video': None})
