from django import template

register = template.Library()


@register.filter
def avatar_url(user):
    """
    Return the profile picture URL for any user in a chat thread -
    the admin's own uploaded picture if they're the site owner,
    otherwise the student's chosen preset Avatar image.
    Returns '' if nothing is set, so templates can fall back to initials.
    """
    if user is None:
        return ''
    admin_profile = getattr(user, 'admin_profile', None)
    if admin_profile and admin_profile.image:
        return admin_profile.image.url
    student_profile = getattr(user, 'profile', None)
    if student_profile and student_profile.avatar and student_profile.avatar.image:
        return student_profile.avatar.image.url
    return ''


@register.filter
def get_item(mapping, key):
    """Look up a value in a dict from a template, e.g. {{ my_dict|get_item:key }}."""
    if mapping is None:
        return ''
    return mapping.get(key, '')
