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
    Upload a real image (preferred) and/or set an emoji as a fallback if no
    image is attached. The name/label is for admin organization only - it is
    never shown to students.
    """
    name = models.CharField(max_length=50, help_text="For your own reference in the admin only - students never see this")
    image = models.ImageField(upload_to='avatars/', blank=True, null=True, help_text="Preferred - a real avatar picture")
    emoji = models.CharField(max_length=10, blank=True, help_text="Fallback shown only if no image is uploaded, e.g. 🦊")
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers show first")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide without deleting")

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} ({'image' if self.image else self.emoji or 'no image/emoji set'})"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    class_level = models.IntegerField(choices=CLASS_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ForeignKey(
        Avatar, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles'
    )
    created_at = models.DateTimeField(auto_now_add=True)

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


class ContactMessage(models.Model):
    """A short message a student sends to the site owner, read in the built-in Inbox page."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.text[:50]}"
