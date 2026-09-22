from django.core.management.base import BaseCommand

from notes.models import Subject, CLASS_CHOICES

# Subjects to add. Edit this list any time you want to add more.
NEW_SUBJECTS = [
    "Hindi",
    "English",
    "Grammar",
    "Vyakaran",
    "IT",
]


class Command(BaseCommand):
    help = (
        "Add a fixed list of subjects (Hindi, English, Grammar, Vyakaran, IT) "
        "for every class (9-12), CBSE board. Safe to re-run - existing "
        "subjects are skipped, nothing is duplicated."
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

    def handle(self, *args, **options):
        board = options['board']
        class_levels = options['classes'] or [c[0] for c in CLASS_CHOICES]

        created_count = 0
        skipped_count = 0

        for class_level in class_levels:
            for subject_name in NEW_SUBJECTS:
                subject, created = Subject.objects.get_or_create(
                    name=subject_name,
                    class_level=class_level,
                    board=board,
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created: {subject}"))
                else:
                    skipped_count += 1
                    self.stdout.write(f"Already exists, skipped: {subject}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created_count} subject(s) created, {skipped_count} already existed."
        ))
