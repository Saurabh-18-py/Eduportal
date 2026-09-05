import os

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.core.cache import cache
from .models import Subject, Chapter, Note, PYQPaper
from django.db import transaction
from .utils import cloudinary_attachment_url
from .forms import BulkNoteUploadForm, BulkPYQUploadForm
from .decorators import uploader_required

# How long the rarely-changing subject/chapter lists stay cached. This is a
# low-level data cache (not a full-page cache), so each user still gets their
# own correct navbar (logged in / logged out, their avatar, etc.) - only the
# underlying DB query result is reused, cutting repeat round-trips to Supabase.
LIST_CACHE_SECONDS = 60 * 30


def class_subjects_view(request, class_level):
    cache_key = f'subjects:class:{class_level}'
    subjects = cache.get(cache_key)
    if subjects is None:
        subjects = list(Subject.objects.filter(class_level=class_level))
        cache.set(cache_key, subjects, LIST_CACHE_SECONDS)
    return render(request, 'notes/subjects.html', {
        'class_level': class_level,
        'subjects': subjects,
    })


def subject_chapters_view(request, subject_id):
    cache_key = f'chapters:subject:{subject_id}'
    cached = cache.get(cache_key)
    if cached is None:
        subject = get_object_or_404(Subject, id=subject_id)
        chapters = list(subject.chapters.all())
        cache.set(cache_key, (subject, chapters), LIST_CACHE_SECONDS)
    else:
        subject, chapters = cached
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


def _clean_title_from_filename(filename):
    name = os.path.splitext(filename)[0]
    name = name.replace('_', ' ').replace('-', ' ').strip()
    return name or filename


@uploader_required
def bulk_upload_view(request):
    """
    Standalone bulk-upload page for Notes and PYQ Papers.
    Only reachable by users in the 'Uploaders' group (or superusers) -
    NOT the same as Django admin access.
    """
    if request.method == 'POST':
        active_tab = request.POST.get('upload_type', 'notes')
    else:
        active_tab = request.GET.get('tab', 'notes')
    if active_tab not in ('notes', 'pyq'):
        active_tab = 'notes'

    notes_form = BulkNoteUploadForm(
        request.POST or None, request.FILES or None,
        prefix='notes'
    ) if active_tab == 'notes' else BulkNoteUploadForm(prefix='notes')

    pyq_form = BulkPYQUploadForm(
        request.POST or None, request.FILES or None,
        prefix='pyq'
    ) if active_tab == 'pyq' else BulkPYQUploadForm(prefix='pyq')

    if request.method == 'POST':
        if active_tab == 'notes' and notes_form.is_valid():
            subject = notes_form.cleaned_data['subject']
            chosen_chapter = notes_form.cleaned_data.get('chapter')
            files = notes_form.cleaned_data['pdf_files']
            created = 0
            chapters_touched = set()
            with transaction.atomic():
                if chosen_chapter:
                    for f in files:
                        title = _clean_title_from_filename(f.name)
                        Note.objects.create(
                            chapter=chosen_chapter,
                            title=title,
                            pdf_file=f,
                        )
                        created += 1
                    chapters_touched.add(chosen_chapter.title)
                else:
                    # Next order number for a new chapter under this subject,
                    # so auto-created chapters land after any existing ones.
                    next_order = (
                        Chapter.objects.filter(subject=subject).count() + 1
                    )
                    for f in files:
                        title = _clean_title_from_filename(f.name)
                        chapter, chapter_created = Chapter.objects.get_or_create(
                            subject=subject,
                            title=title,
                            defaults={'order': next_order},
                        )
                        if chapter_created:
                            next_order += 1
                        Note.objects.create(
                            chapter=chapter,
                            title=title,
                            pdf_file=f,
                        )
                        created += 1
                        chapters_touched.add(chapter.title)
            messages.success(
                request,
                f"Uploaded {created} note(s) to {subject} "
                f"({len(chapters_touched)} chapter(s))."
            )
            cache.delete(f'chapters:subject:{subject.id}')
            return redirect('notes:bulk_upload')

        elif active_tab == 'pyq' and pyq_form.is_valid():
            subject = pyq_form.cleaned_data['subject']
            class_level = pyq_form.cleaned_data['class_level']
            year = pyq_form.cleaned_data['year']
            set_label = pyq_form.cleaned_data['set_label']
            files = pyq_form.cleaned_data['pdf_files']
            created = 0
            for f in files:
                PYQPaper.objects.create(
                    subject=subject,
                    class_level=class_level,
                    year=year,
                    set_label=set_label,
                    pdf_file=f,
                )
                created += 1
            messages.success(request, f"Uploaded {created} PYQ paper(s).")
            return redirect('notes:bulk_upload')

    subjects_data = list(Subject.objects.values('id', 'name', 'class_level'))
    chapters_data = list(
        Chapter.objects.order_by('order', 'id').values('id', 'title', 'subject_id')
    )

    return render(request, 'notes/bulk_upload.html', {
        'notes_form': notes_form,
        'pyq_form': pyq_form,
        'active_tab': active_tab,
        'subjects_data': subjects_data,
        'chapters_data': chapters_data,
    })
