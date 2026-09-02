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
    emoji = models.CharField(max_length=10, help_text="The emoji shown as the avatar, e.g. 🦊")
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

    def __str__(self):
        return f"{self.user.username} - Class {self.class_level}"


class UploaderAccount(User):
    """
    A proxy over Django's built-in User, shown in the admin as a separate,
    simplified "Uploaders" section. Creating a user here can NEVER grant
    staff/admin access - the admin form for this model doesn't even show
    those fields, and save_model() (in accounts/admin.py) forces them off
    and puts the user in the 'Uploaders' group automatically.
    """

    class Meta:
        proxy = True
        verbose_name = 'Uploader (Notes upload access only)'
        verbose_name_plural = 'Uploaders (Notes upload access only)'
