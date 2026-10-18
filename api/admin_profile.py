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
    """The admin whose profile is shown: the first superuser that already has a photo/video, else the first superuser."""
    admins = list(get_user_model().objects.filter(is_superuser=True).order_by('id'))
    for u in admins:
        ap = getattr(u, 'admin_profile', None)
        if ap and (ap.image or ap.video or ap.video_link):
            return u
    return admins[0] if admins else None


def _cld_mp4(url):
    """Cloudinary video -> delivered as mp4 (plays on every phone, even if the original was .mov)."""
    if '/video/upload/' in url and 'f_mp4' not in url:
        url = url.replace('/video/upload/', '/video/upload/f_mp4,q_auto/', 1)
        url = re.sub(r'\.[A-Za-z0-9]{2,4}(\?.*)?$', '.mp4', url)
    return url


def _video_info(ap, request):
    if not ap:
        return None
    if ap.video_link:
        m = YT_RE.search(ap.video_link)
        if m:
            return {'kind': 'youtube', 'url': ap.video_link, 'youtube_id': m.group(1)}
        return {'kind': 'link', 'url': _cld_mp4(ap.video_link), 'youtube_id': None}
    if ap.video:
        url = ap.video.url
        url = request.build_absolute_uri(url) if url.startswith('/') else url
        return {'kind': 'file', 'url': _cld_mp4(url), 'youtube_id': None}
    return None


def avatar_video_url(request, size=200, seconds=8):
    """Small square video for the admin's round avatar in Messages (None if there is no playable video)."""
    admin = _owner()
    ap = getattr(admin, 'admin_profile', None) if admin else None
    info = _video_info(ap, request)
    if not info or info['kind'] == 'youtube':
        return None
    url = info['url'].replace('/video/upload/f_mp4,q_auto/', '/video/upload/')
    if '/video/upload/' in url:
        # Cloudinary: tiny 200x200 clip, first 8 seconds, light quality -> loads fast and loops nicely
        url = url.replace('/video/upload/', f'/video/upload/w_{size},h_{size},c_fill,du_{seconds},q_auto:low,f_mp4/', 1)
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
        "Hey! Main Saurabh hu, EduPortal ka banane wala. Ye poora app aur website mai akela "
        "banata aur chalata hu, isliye yahan jo bhi notes, tests aur doubt solver hai, sab "
        "tumhare liye hi banaya hai.\n\n"
        "Koi galti dikhe, kisi chapter ke notes ya test chahiye, ya bas kuch poochna ho, "
        "seedha mujhe message karo. Tumhara message mere paas hi aata hai."
    )
    HIGHLIGHTS = [
        'Class 9 se 12 (CBSE) ke chapter-wise notes aur mock tests',
        'Doubt aaye to AI doubt solver se pooch lo',
        'Kuch galat lage ya suggestion ho, to mujhe message karo',
    ]

    def get(self, request):
        admin = _owner()
        ap = getattr(admin, 'admin_profile', None) if admin else None
        avatar_url = request.build_absolute_uri(ap.image.url) if ap and ap.image else None

        stats = cache.get('admin_profile_stats_v2')
        if stats is None:
            stats = {
                'notes': Note.objects.count(),
                'tests': Test.objects.count(),
                'questions': Question.objects.count(),
            }
            cache.set('admin_profile_stats_v2', stats, 600)

        return Response({
            'name': (admin.first_name if admin and admin.first_name else self.DISPLAY_NAME),
            'title': self.TITLE,
            'bio': self.BIO,
            'avatar_url': avatar_url,
            'highlights': self.HIGHLIGHTS,
            'stats': stats,
            'video': _video_info(ap, request),
            'avatar_video_url': avatar_video_url(request, size=400, seconds=10),
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
        ap, _ = AdminProfile.objects.get_or_create(user=_owner() or request.user)
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
        ap = AdminProfile.objects.filter(user=_owner() or request.user).first()
        if ap:
            self._drop_file(ap)
            ap.video = None
            ap.video_link = ''
            ap.save()
        return Response({'video': None})


class AdminVideoSignView(APIView):
    """GET /api/admin/profile-video/sign/ -> signed params so the app can upload a video straight to Cloudinary."""
    permission_classes = [IsSuperuser]

    def get(self, request):
        import hashlib
        import time
        from django.conf import settings

        cfg = getattr(settings, 'CLOUDINARY_STORAGE', {}) or {}
        cloud, key, secret = cfg.get('CLOUD_NAME'), cfg.get('API_KEY'), cfg.get('API_SECRET')
        if not (cloud and key and secret):
            return Response({'error': 'Cloudinary is not configured on the server.'}, status=400)
        folder = 'admin_videos'
        ts = int(time.time())
        signature = hashlib.sha1(f'folder={folder}&timestamp={ts}{secret}'.encode()).hexdigest()
        return Response({'cloud_name': cloud, 'api_key': key, 'timestamp': ts, 'folder': folder, 'signature': signature})
