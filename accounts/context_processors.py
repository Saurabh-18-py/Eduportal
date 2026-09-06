from .models import Message


def unread_messages(request):
    """
    Adds `unread_message_count` to every template's context - works the same
    way for a student (unread replies from admin) and for the admin (unread
    messages from any student), since both just count messages addressed to
    the logged-in user that haven't been read yet.
    """
    if not request.user.is_authenticated:
        return {}
    count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return {'unread_message_count': count}
