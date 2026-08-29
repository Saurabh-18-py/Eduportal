from django.db import models
from django.conf import settings

if settings.CLOUDINARY_STORAGE.get('CLOUD_NAME'):
    from cloudinary_storage.storage import RawMediaCloudinaryStorage
    PDF_STORAGE = RawMediaCloudinaryStorage()
else:
    PDF_STORAGE = None

CLASS_CHOICES = [
    (9, 'Class 9'),
    (10, 'Class 10'),
    (11, 'Class 11'),
    (12, 'Class 12'),
]

BOARD_CHOICES = [
    ('CBSE', 'CBSE'),
]


class Subject(models.Model):
    name = models.CharField(max_length=100)
    class_level = models.IntegerField(choices=CLASS_CHOICES)
    board = models.CharField(max_length=20, choices=BOARD_CHOICES, default='CBSE')

    class Meta:
        ordering = ['class_level', 'name']
        unique_together = ('name', 'class_level', 'board')

    def __str__(self):
        return f"{self.name} (Class {self.class_level} - {self.board})"


class Chapter(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.subject.name} - {self.title}"


class Note(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='notes_pdfs/', storage=PDF_STORAGE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PYQPaper(models.Model):
    class_level = models.IntegerField(choices=CLASS_CHOICES)
    year = models.PositiveIntegerField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='pyq_papers')
    set_label = models.CharField(max_length=50, blank=True, help_text='Optional, e.g. "Set 1" if multiple sets exist')
    pdf_file = models.FileField(upload_to='pyq_papers/', storage=PDF_STORAGE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'subject__name']

    def __str__(self):
        label = f" ({self.set_label})" if self.set_label else ""
        return f"{self.subject.name} {self.year}{label} - Class {self.class_level}"
