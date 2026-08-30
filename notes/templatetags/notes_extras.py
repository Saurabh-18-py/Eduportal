from django import template
from notes.utils import cloudinary_attachment_url

register = template.Library()


@register.filter
def cloudinary_download(url):
    return cloudinary_attachment_url(url)
