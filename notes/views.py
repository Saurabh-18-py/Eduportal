from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import Subject, Chapter, Note, PYQPaper
from .utils import cloudinary_attachment_url


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


def pyq_years_view(request, class_level):
    years = list(range(2025, 2019, -1))  # 2025 down to 2020
    available_years = set(
        PYQPaper.objects.filter(class_level=class_level).values_list('year', flat=True)
    )
    return render(request, 'notes/pyq_years.html', {
        'class_level': class_level,
        'years': years,
        'available_years': available_years,
    })


def pyq_subjects_view(request, class_level, year):
    papers = PYQPaper.objects.filter(class_level=class_level, year=year).select_related('subject')
    return render(request, 'notes/pyq_subjects.html', {
        'class_level': class_level,
        'year': year,
        'papers': papers,
    })


def view_note_pdf(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    return render(request, 'notes/view_pdf.html', {
        'page_title': note.title,
        'back_url': reverse('notes:chapter_notes', args=[note.chapter_id]),
        'pdf_url': note.pdf_file.url,
        'download_url': cloudinary_attachment_url(note.pdf_file.url),
    })


def view_pyq_pdf(request, paper_id):
    paper = get_object_or_404(PYQPaper, id=paper_id)
    label = f" ({paper.set_label})" if paper.set_label else ""
    return render(request, 'notes/view_pdf.html', {
        'page_title': f"{paper.subject.name} {paper.year}{label}",
        'back_url': reverse('notes:pyq_subjects', args=[paper.class_level, paper.year]),
        'pdf_url': paper.pdf_file.url,
        'download_url': cloudinary_attachment_url(paper.pdf_file.url),
    })
