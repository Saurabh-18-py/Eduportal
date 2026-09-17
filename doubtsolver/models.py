from django.conf import settings
from django.db import models


class DoubtMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'Student'),
        ('assistant', 'AI Tutor'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doubt_messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.student.username} [{self.role}]: {self.content[:40]}"
