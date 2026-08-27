from django.shortcuts import render, get_object_or_404
from .models import Subject, Chapter


def class_subjects_view(request, class_level):
    subjects = Subject.objects.filter(class_level=class_level)
    return render(request, 'notes/subjects.html', {
        'class_level': class_level,
        'subjects': subjects,
    })


def subject_chapters_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    chapters = subject.chapters.all()
    return render(request, 'notes/chapters.html', {
        'subject': subject,
        'chapters': chapters,
    })


def chapter_notes_view(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    notes = chapter.notes.all()
    return render(request, 'notes/notes_list.html', {
        'chapter': chapter,
        'notes': notes,
    })
