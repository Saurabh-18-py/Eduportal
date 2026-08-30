from django.db import models
from django.contrib.auth.models import User

CLASS_CHOICES = [
    (9, 'Class 9'),
    (10, 'Class 10'),
    (11, 'Class 11'),
    (12, 'Class 12'),
]

# Preset avatars a student can pick from. No image upload - just a fixed
# set of emoji avatars identified by a short key stored on the profile.
AVATAR_CHOICES = [
    ('fox', 'Fox'),
    ('owl', 'Owl'),
    ('cat', 'Cat'),
    ('panda', 'Panda'),
    ('lion', 'Lion'),
    ('koala', 'Koala'),
    ('tiger', 'Tiger'),
    ('rabbit', 'Rabbit'),
]

AVATAR_EMOJI = {
    'fox': '🦊',
    'owl': '🦉',
    'cat': '🐱',
    'panda': '🐼',
    'lion': '🦁',
    'koala': '🐨',
    'tiger': '🐯',
    'rabbit': '🐰',
}


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    class_level = models.IntegerField(choices=CLASS_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.CharField(max_length=20, choices=AVATAR_CHOICES, default='fox')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def avatar_emoji(self):
        return AVATAR_EMOJI.get(self.avatar, AVATAR_EMOJI['fox'])

    def __str__(self):
        return f"{self.user.username} - Class {self.class_level}"
