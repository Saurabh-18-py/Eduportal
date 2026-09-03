import datetime

from django.db import models
from django.contrib.auth.models import User
from notes.models import Subject

# How many questions a student sees per day, once a test has more than this
# many questions banked. The rest rotate in on later days.
DAILY_QUESTION_COUNT = 10


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
    def daily_question_count(self):
        """How many questions actually show today (for display, e.g. in the test list)."""
        return min(DAILY_QUESTION_COUNT, self.total_questions)

    def get_daily_questions(self):
        """
        Today's rotating subset of questions - same set for every student on a
        given day, cycling through the full question bank over multiple days
        so a 100-question bank shows a fresh batch of 10 roughly every 10 days.
        If the test doesn't have more than DAILY_QUESTION_COUNT questions yet,
        all of them are shown (nothing to rotate).
        """
        all_questions = list(
            self.questions.prefetch_related('choices').order_by('order')
        )
        total = len(all_questions)
        if total <= DAILY_QUESTION_COUNT:
            return all_questions

        num_buckets = (total + DAILY_QUESTION_COUNT - 1) // DAILY_QUESTION_COUNT
        day_index = datetime.date.today().toordinal()
        bucket = day_index % num_buckets
        start = bucket * DAILY_QUESTION_COUNT
        selected = all_questions[start:start + DAILY_QUESTION_COUNT]
        if len(selected) < DAILY_QUESTION_COUNT:
            selected += all_questions[:DAILY_QUESTION_COUNT - len(selected)]
        return selected


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
