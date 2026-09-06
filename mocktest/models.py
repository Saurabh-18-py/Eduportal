import math

from django.db import models
from django.contrib.auth.models import User
from notes.models import Subject

# Each 10-question block of a chapter's question bank becomes its own
# selectable "Test N" - so a 100-question chapter shows as Test 1 through
# Test 10, all available at once (no daily waiting).
QUESTIONS_PER_TEST = 10


class Test(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='tests')
    duration_minutes = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def total_questions(self):
        return self.questions.count()

    @property
    def num_slices(self):
        """How many separate 'Test N' entries this chapter's question bank splits into."""
        total = self.total_questions
        if total == 0:
            return 0
        return math.ceil(total / QUESTIONS_PER_TEST)

    def get_slice_questions(self, slice_number):
        """
        Returns the fixed set of questions for 'Test <slice_number>' (1-indexed):
        slice 1 = questions 1-10, slice 2 = questions 11-20, etc. Always the
        same questions for that slice number, for every student, every time -
        no date/rotation involved.
        """
        all_questions = list(
            self.questions.prefetch_related('choices').order_by('order')
        )
        start = (slice_number - 1) * QUESTIONS_PER_TEST
        return all_questions[start:start + QUESTIONS_PER_TEST]


class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class TestAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.student.username} - {self.test.title} ({self.score}/{self.total})"


class StudentAnswer(models.Model):
    attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def is_correct(self):
        return bool(self.selected_choice and self.selected_choice.is_correct)
