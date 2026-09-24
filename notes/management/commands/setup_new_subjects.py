from django.core.management.base import BaseCommand

from notes.models import Subject, Chapter
from notes.new_subjects_syllabus import NEW_SUBJECTS_SYLLABUS


class Command(BaseCommand):
    help = (
        "Create Subject AND Chapter records for the new subjects "
        "(Hindi, English, Grammar, Vyakaran, IT) across Class 9-12, CBSE board. "
        "Safe to re-run - nothing already existing is duplicated. "
        "Run this FIRST, before generate_all_mcqs / generate_notes / "
        "generate_subjective_questions for these subjects."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--board', type=str, default='CBSE',
            help="Board to add subjects under (default: CBSE)",
        )
        parser.add_argument(
            '--classes', type=int, nargs='+', default=None,
            help="Specific class levels to add (default: all - 9, 10, 11, 12)",
        )
        parser.add_argument(
            '--subject', type=str, default=None,
            help='Limit to one subject, e.g. "Hindi" (default: all 5 new subjects)',
        )

    def handle(self, *args, **options):
        board = options['board']
        class_levels = options['classes'] or list(NEW_SUBJECTS_SYLLABUS.keys())
        subject_filter = options['subject']

        subjects_created = 0
        chapters_created = 0
        chapters_skipped = 0

        for class_level in class_levels:
            if class_level not in NEW_SUBJECTS_SYLLABUS:
                self.stdout.write(self.style.WARNING(f"No data for Class {class_level}, skipping."))
                continue

            subjects_map = NEW_SUBJECTS_SYLLABUS[class_level]
            if subject_filter:
                if subject_filter not in subjects_map:
                    self.stdout.write(self.style.WARNING(
                        f"Subject '{subject_filter}' not found for Class {class_level}, skipping."
                    ))
                    continue
                subjects_map = {subject_filter: subjects_map[subject_filter]}

            for subject_name, chapters in subjects_map.items():
                subject, created = Subject.objects.get_or_create(
                    name=subject_name, class_level=class_level, board=board,
                )
                if created:
                    subjects_created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created subject: {subject}"))

                for order, chapter_title in enumerate(chapters, start=1):
                    chapter, chapter_created = Chapter.objects.get_or_create(
                        subject=subject, title=chapter_title,
                        defaults={'order': order},
                    )
                    if chapter_created:
                        chapters_created += 1
                    else:
                        chapters_skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Subjects created: {subjects_created}. "
            f"Chapters created: {chapters_created}, already existed: {chapters_skipped}."
        ))
