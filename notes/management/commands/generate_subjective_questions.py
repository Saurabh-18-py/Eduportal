import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject, Chapter, Note
from notes.subjective_ai import generate_full_subjective_set, questions_to_pdf_sections
from notes.pdf_builder import build_notes_pdf
from mocktest.ai_helpers import load_api_keys, MCQGenerationError

NOTE_TITLE_SUFFIX = "Subjective Questions"
TARGET_QUESTIONS_PER_CHAPTER = 50
BATCH_SIZE = 15


class Command(BaseCommand):
    help = "Bulk-generate AI subjective (long/short answer) questions with model answers, as PDFs, for chapters already in the database."

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_level', type=int, default=None, help='Limit to one class, e.g. 11 (default: all classes)')
        parser.add_argument('--subject', default=None, help='Limit to one subject, e.g. "History" (default: all subjects)')
        parser.add_argument('--count', type=int, default=TARGET_QUESTIONS_PER_CHAPTER, help=f'Target questions per chapter (default {TARGET_QUESTIONS_PER_CHAPTER})')
        parser.add_argument('--delay', type=int, default=15, help='Seconds to wait between batches/chapters, to stay within free-tier rate limits (default 15)')

    def handle(self, *args, **options):
        api_keys = load_api_keys()
        if not api_keys:
            raise CommandError(
                "No Groq API key configured.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEYS='key_one,key_two,...'\n"
            )
        key_index = [0]

        class_level = options['class_level']
        subject_filter = options['subject']
        delay = options['delay']
        target_count = options['count']

        chapters = Chapter.objects.select_related('subject').all()
        if class_level:
            chapters = chapters.filter(subject__class_level=class_level)
        if subject_filter:
            chapters = chapters.filter(subject__name=subject_filter)
        chapters = chapters.order_by('subject__class_level', 'subject__name', 'order', 'id')

        total = chapters.count()
        if total == 0:
            raise CommandError("No matching chapters found - check your --class/--subject filters.")

        self.stdout.write(f"Starting bulk subjective-questions generation: {total} chapters, target {target_count} questions each.\n")

        done = 0
        skipped = 0
        failed = []
        progress = 0

        def on_rotate(old_idx, new_idx):
            self.stdout.write(self.style.WARNING(f"    key {old_idx} exhausted, rotating to key {new_idx}..."))

        def on_batch(batch_num, collected_so_far):
            self.stdout.write(f"    batch {batch_num}: {collected_so_far}/{target_count} collected so far...")
            time.sleep(delay)

        for chapter in chapters:
            progress += 1
            subject_name = chapter.subject.name
            note_title = f"{chapter.title} - {NOTE_TITLE_SUFFIX}"
            label = f"Class {chapter.subject.class_level} {subject_name} - {chapter.title}"

            if Note.objects.filter(chapter=chapter, title=note_title).exists():
                self.stdout.write(f"[{progress}/{total}] skip - {label} (already exists)")
                skipped += 1
                continue

            self.stdout.write(f"[{progress}/{total}] Generating: {label} (target {target_count}) ...")

            try:
                questions = generate_full_subjective_set(
                    api_keys, key_index, subject_name, chapter.title, chapter.subject.class_level,
                    target_count=target_count, batch_size=BATCH_SIZE,
                    on_rotate=on_rotate, on_batch=on_batch,
                )
            except MCQGenerationError as e:
                self.stdout.write(self.style.ERROR(f"    FAILED: {e}"))
                failed.append(label)
                continue

            if not questions:
                self.stdout.write(self.style.ERROR("    FAILED: no questions generated."))
                failed.append(label)
                continue

            if len(questions) < target_count:
                self.stdout.write(self.style.WARNING(
                    f"    only got {len(questions)}/{target_count} unique questions (AI ran out of new angles) - saving what we have."
                ))

            try:
                sections = questions_to_pdf_sections(questions)
                pdf_file = build_notes_pdf(
                    subject_name, chapter.title, chapter.subject.class_level, sections,
                    doc_label="SUBJECTIVE QUESTIONS",
                )
                with transaction.atomic():
                    note = Note(chapter=chapter, title=note_title)
                    note.pdf_file.save(pdf_file.name, pdf_file, save=True)
                self.stdout.write(self.style.SUCCESS(f"    done - {len(questions)} questions saved as PDF."))
                done += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    FAILED to build/save PDF: {e}"))
                failed.append(label)

        self.stdout.write("\n" + self.style.SUCCESS(f"Finished. Created: {done}, Skipped (already existed): {skipped}, Failed: {len(failed)}"))
        if failed:
            self.stdout.write(self.style.ERROR("Failed chapters (re-run with --subject \"<name>\" --class <N> for these):"))
            for f in failed:
                self.stdout.write(f"  - {f}")
