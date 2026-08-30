from django.db import models
from django.contrib.auth.models import User

CLASS_CHOICES = [
    (9, 'Class 9'),
    (10, 'Class 10'),
    (11, 'Class 11'),
    (12, 'Class 12'),
]


class Avatar(models.Model):
    """
    A preset profile picture option. Managed entirely from the Django admin -
    add, edit, remove, reorder, or disable avatars any time without touching code.
    """
    name = models.CharField(max_length=50, help_text="e.g. Fox, Owl - shown as a label under the avatar")
    emoji = models.CharField(max_length=10, blank=True, help_text="Optional fallback emoji, e.g. 🦊 (used only if no image is uploaded)")
    image = models.ImageField(upload_to='avatars/', blank=True, null=True, help_text="Upload a profile picture image (preferred over emoji)")
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers show first")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide without deleting")

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.emoji} {self.name}"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    class_level = models.IntegerField(choices=CLASS_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ForeignKey(
        Avatar, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def avatar_emoji(self):
        return self.avatar.emoji if self.avatar else '🙂'

    @property
    def avatar_image_url(self):
        if self.avatar and self.avatar.image:
            return self.avatar.image.url
        return None

    def __str__(self):
        return f"{self.user.username} - Class {self.class_level}"
