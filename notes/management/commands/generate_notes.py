import os
import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject, Chapter, Note
from notes.notes_ai import generate_notes_batch_with_rotation
from notes.pdf_builder import build_notes_pdf
from mocktest.ai_helpers import load_api_keys, MCQGenerationError, RateLimitError
from mocktest.management.commands.generate_all_mcqs import SYLLABUS

CLASS_LEVEL = 11  # this command is Class 11 only, on purpose


class Command(BaseCommand):
    help = "Bulk-generate detailed AI notes (with examples), as PDFs, for Class 11 chapters."

    def add_arguments(self, parser):
        parser.add_argument('--subject', default=None, help='Limit to one subject, e.g. "History" (default: all Class 11 subjects)')
        parser.add_argument('--delay', type=int, default=20, help='Seconds to wait between chapters, to stay within free-tier rate limits (default 20)')

    def handle(self, *args, **options):
        api_keys = load_api_keys()
        if not api_keys:
            raise CommandError(
                "No Groq API key configured.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'\n"
                "or GROQ_API_KEYS='key_one,key_two' for multiple.\n"
            )
        key_index = [0]

        subject_filter = options['subject']
        delay = options['delay']

        subjects_map = SYLLABUS[CLASS_LEVEL]
        if subject_filter:
            if subject_filter not in subjects_map:
                raise CommandError(f"Subject '{subject_filter}' not found for Class 11. Available: {list(subjects_map.keys())}")
            subjects_map = {subject_filter: subjects_map[subject_filter]}

        total_chapters = sum(len(chapters) for chapters in subjects_map.values())
        self.stdout.write(f"Starting bulk notes generation: {total_chapters} chapters across {len(subjects_map)} subject(s) for Class 11.\n")

        done = 0
        failed = []
        skipped = 0
        progress = 0

        def on_rotate(old_idx, new_idx):
            self.stdout.write(self.style.WARNING(f"    key {old_idx} exhausted, rotating to key {new_idx}..."))

        for subject_name, chapters in subjects_map.items():
            subject, created = Subject.objects.get_or_create(
                name=subject_name,
                class_level=CLASS_LEVEL,
                board='CBSE',
            )
            if created:
                self.stdout.write(self.style.WARNING(f"Created subject: {subject}"))

            for chapter_title in chapters:
                progress += 1
                note_title = f"{chapter_title} - Notes"
                if len(note_title) > 95:
                    note_title = f"{chapter_title[:87].rstrip()}... - Notes"

                chapter, _ = Chapter.objects.get_or_create(
                    subject=subject,
                    title=chapter_title,
                )

                if Note.objects.filter(chapter=chapter, title=note_title).exists():
                    self.stdout.write(f"[{progress}/{total_chapters}] skip - {subject_name} - {chapter_title} (already exists)")
                    skipped += 1
                    continue

                self.stdout.write(f"[{progress}/{total_chapters}] Generating: {subject_name} - {chapter_title} ...")

                sections = None
                max_retries = 4
                for attempt in range(1, max_retries + 1):
                    try:
                        sections, _meta = generate_notes_batch_with_rotation(
                            api_keys, key_index, subject_name, chapter_title, CLASS_LEVEL, on_rotate=on_rotate
                        )
                        break
                    except RateLimitError as e:
                        wait_for = e.retry_after + 2
                        self.stdout.write(self.style.WARNING(
                            f"    rate limited, waiting {wait_for:.0f}s before retry ({attempt}/{max_retries})..."
                        ))
                        time.sleep(wait_for)
                    except MCQGenerationError as e:
                        self.stdout.write(self.style.ERROR(f"    FAILED: {e}"))
                        failed.append(f"{subject_name} - {chapter_title}")
                        break
                    except requests.exceptions.RequestException as e:
                        self.stdout.write(self.style.WARNING(
                            f"    network hiccup ({e.__class__.__name__}), retrying in 10s ({attempt}/{max_retries})..."
                        ))
                        time.sleep(10)

                if sections is None:
                    if f"{subject_name} - {chapter_title}" not in failed:
                        self.stdout.write(self.style.ERROR(f"    FAILED after {max_retries} retries (rate limit)."))
                        failed.append(f"{subject_name} - {chapter_title}")
                    time.sleep(delay)
                    continue

                try:
                    pdf_file = build_notes_pdf(subject_name, chapter_title, CLASS_LEVEL, sections)
                    with transaction.atomic():
                        note = Note(chapter=chapter, title=note_title)
                        note.pdf_file.save(pdf_file.name, pdf_file, save=True)
                    self.stdout.write(self.style.SUCCESS(f"    done - {len(sections)} sections saved as PDF."))
                    done += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    FAILED to build/save PDF: {e}"))
                    failed.append(f"{subject_name} - {chapter_title}")

                time.sleep(delay)

        self.stdout.write("\n" + self.style.SUCCESS(f"Finished. Created: {done}, Skipped (already existed): {skipped}, Failed: {len(failed)}"))
        if failed:
            self.stdout.write(self.style.ERROR("Failed chapters (re-run generate_notes --subject \"<name>\" for these):"))
            for f in failed:
                self.stdout.write(f"  - {f}")
