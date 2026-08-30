import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from notes.models import Subject, Chapter, Note
from mocktest.ai_helpers import MCQGenerationError, RateLimitError
from mocktest.notes_ai_helpers import generate_notes_via_groq
from mocktest.notes_pdf_builder import build_notes_pdf


class Command(BaseCommand):
    help = "Auto-generate slide-style chapter notes (PDF) for ONE chapter using Groq AI and save to the database."

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Subject name, e.g. "Science"')
        parser.add_argument('--chapter', required=True, help='Chapter/topic name')
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: 9, 10, 11 or 12')
        parser.add_argument('--pyqs', type=int, default=2, help='Number of PYQ slides to include (default 2)')

    def handle(self, *args, **options):
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise CommandError(
                "GROQ_API_KEY environment variable not set.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'"
            )

        subject_name = options['subject']
        chapter_name = options['chapter']
        class_level = options['class_level']
        num_pyq = options['pyqs']

        subject, created = Subject.objects.get_or_create(
            name=subject_name, class_level=class_level, board='CBSE',
        )
        if created:
            self.stdout.write(self.style.WARNING(f"Created new subject: {subject}"))

        chapter, _ = Chapter.objects.get_or_create(subject=subject, title=chapter_name)

        self.stdout.write(f"Asking Groq AI to generate notes for '{chapter_name}' (Class {class_level} {subject_name})...")

        try:
            data = generate_notes_via_groq(api_key, subject_name, chapter_name, class_level, num_pyq)
        except RateLimitError as e:
            raise CommandError(f"Rate limited: {e}")
        except MCQGenerationError as e:
            raise CommandError(str(e))

        safe_chapter = "".join(ch if ch.isalnum() else "_" for ch in chapter_name)[:60]
        output_path = f"/tmp/notes_{class_level}_{subject_name}_{safe_chapter}.pdf"

        self.stdout.write("Building PDF...")
        build_notes_pdf(data, output_path, class_level, subject_name, chapter_name)

        with open(output_path, 'rb') as f:
            pdf_content = f.read()

        note = Note.objects.create(
            chapter=chapter,
            title=f"{chapter_name} - Notes",
        )
        note.pdf_file.save(f"{safe_chapter}_notes.pdf", ContentFile(pdf_content), save=True)

        self.stdout.write(self.style.SUCCESS(f"Notes created and saved: {note.title} (Note id {note.id})"))
