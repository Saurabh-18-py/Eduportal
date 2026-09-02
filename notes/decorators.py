from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

UPLOADER_GROUP_NAME = 'Uploaders'


def uploader_required(view_func):
    """
    Allows access only to logged-in users in the 'Uploaders' group
    (or superusers). Deliberately does NOT check is_staff, so these
    users never get access to /admin/ itself.
    """
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_superuser or user.groups.filter(name=UPLOADER_GROUP_NAME).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You don't have access to the upload page.")
    return _wrapped
