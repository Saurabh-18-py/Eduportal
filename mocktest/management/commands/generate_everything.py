from django.core.management import call_command
from django.core.management.base import BaseCommand

from notes.new_subjects_syllabus import NEW_SUBJECTS_SYLLABUS


class Command(BaseCommand):
    help = (
        "Run the full pipeline (create test shells + topup to target questions) "
        "for every class and every new subject (Hindi, English, Grammar, Vyakaran, IT) "
        "in one go. Safe to re-run any time - already-completed chapters are skipped "
        "quickly, so if it stops partway (rate limits, connection drop, etc.) just "
        "run the exact same command again to resume from where it left off."
    )

    def add_arguments(self, parser):
        parser.add_argument('--classes', type=int, nargs='+', default=None, help='Limit to specific classes, e.g. --classes 9 10 (default: 9, 10, 11, 12)')
        parser.add_argument('--subjects', type=str, nargs='+', default=None, help='Limit to specific subjects, e.g. --subjects Hindi English (default: all 5 new subjects)')
        parser.add_argument('--target', type=int, default=100, help='Target question count per chapter/test (default: 100)')

    def handle(self, *args, **options):
        class_levels = options['classes'] or list(NEW_SUBJECTS_SYLLABUS.keys())
        subject_filter = options['subjects']
        target = options['target']

        combos = []
        for class_level in class_levels:
            if class_level not in NEW_SUBJECTS_SYLLABUS:
                continue
            subjects = list(NEW_SUBJECTS_SYLLABUS[class_level].keys())
            if subject_filter:
                subjects = [s for s in subjects if s in subject_filter]
            for subject in subjects:
                combos.append((class_level, subject))

        total = len(combos)
        self.stdout.write(self.style.SUCCESS(
            f"Running full pipeline for {total} class+subject combination(s), target {target} questions each.\n"
        ))

        succeeded = []
        failed = []

        for i, (class_level, subject) in enumerate(combos, start=1):
            self.stdout.write(self.style.HTTP_INFO(
                f"\n===== [{i}/{total}] Class {class_level} - {subject} ====="
            ))
            try:
                call_command('generate_all_mcqs', class_level=class_level, subject=subject)
                call_command('topup_questions', class_levels=[class_level], subject=subject, target=target)
                succeeded.append(f"Class {class_level} - {subject}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ERROR on Class {class_level} - {subject}: {e}"))
                self.stdout.write(self.style.WARNING("    Continuing with the next subject...\n"))
                failed.append(f"Class {class_level} - {subject} ({e})")

        self.stdout.write(self.style.SUCCESS(
            f"\n\n===== DONE. {len(succeeded)}/{total} combinations completed cleanly. ====="
        ))
        if failed:
            self.stdout.write(self.style.ERROR("These had an error partway through (re-run this same command to retry - already-done chapters are skipped automatically):"))
            for f in failed:
                self.stdout.write(f"  - {f}")
