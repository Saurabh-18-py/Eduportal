import time

from django.core.management.base import BaseCommand, CommandError

from mocktest.models import Test, Question
from mocktest.ai_helpers import (
    load_api_keys,
    audit_questions_batch_with_rotation,
    MCQGenerationError,
    RateLimitError,
    InvalidAPIKeyError,
)


class Command(BaseCommand):
    help = (
        "Uses AI to check existing questions against the correct grade-level "
        "syllabus (catches things like Class 11-12 concepts leaking into a "
        "Class 9-10 question) - far more reliable than keyword matching, and "
        "cheap since it's classification, not generation. By default this "
        "only REPORTS flagged questions; pass --auto-delete to remove them. "
        "Supports the same GROQ_API_KEYS rotation as topup_questions. If "
        "rate-limited partway through, re-run with --start-id <the last id "
        "shown> to resume."
    )

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_levels', type=int, nargs='+', default=[9, 10], help='Class(es) to audit (default: 9 10 - the ones at risk of higher-class concepts leaking in)')
        parser.add_argument('--subject', default=None, help='Limit to one subject name (default: all)')
        parser.add_argument('--batch-size', type=int, default=20, help='Questions per API call (default 20)')
        parser.add_argument('--delay', type=int, default=15, help='Seconds between API calls (default 15)')
        parser.add_argument('--start-id', type=int, default=0, help='Only audit questions with id greater than this (for resuming a stopped run)')
        parser.add_argument('--auto-delete', action='store_true', default=False, help='Delete flagged questions automatically. Without this flag, it only reports them.')

    def handle(self, *args, **options):
        api_keys = load_api_keys()
        if not api_keys:
            raise CommandError(
                "No Groq API key found. Set GROQ_API_KEY or GROQ_API_KEYS.\n"
            )
        key_index = [0]

        class_levels = options['class_levels']
        batch_size = options['batch_size']
        delay = options['delay']
        start_id = options['start_id']
        auto_delete = options['auto_delete']

        tests = Test.objects.select_related('subject').filter(
            subject__class_level__in=class_levels
        ).order_by('subject__class_level', 'subject__name', 'title')
        if options['subject']:
            tests = tests.filter(subject__name__iexact=options['subject'])

        def on_rotate(old_idx, new_idx):
            self.stdout.write(self.style.WARNING(
                f"  Key #{old_idx + 1}/{len(api_keys)} is rate-limited, switching to key #{new_idx + 1}..."
            ))

        total_checked = 0
        total_flagged = 0
        total_deleted = 0
        last_id_seen = start_id

        for test in tests:
            questions = list(
                test.questions.filter(id__gt=start_id).order_by('id')
            )
            if not questions:
                continue

            topic = test.title.replace(' - Practice Test', '').strip()

            for i in range(0, len(questions), batch_size):
                chunk = questions[i:i + batch_size]
                self.stdout.write(
                    f"[Class {test.subject.class_level} | {test.subject.name}] {topic}: "
                    f"checking questions {chunk[0].id}-{chunk[-1].id} ({len(chunk)})..."
                )

                try:
                    results, meta = audit_questions_batch_with_rotation(
                        api_keys, key_index, test.subject.name, topic, test.subject.class_level,
                        [q.text for q in chunk], on_rotate=on_rotate,
                    )
                except (RateLimitError, InvalidAPIKeyError) as e:
                    self.stdout.write(self.style.WARNING(
                        f"\nAll {len(api_keys)} API key(s) are unusable right now (rate-limited or invalid). Stopping here.\n"
                        f"Re-run with --start-id {last_id_seen} to resume from here.\n({e})"
                    ))
                    self._summary(total_checked, total_flagged, total_deleted)
                    return
                except MCQGenerationError as e:
                    self.stdout.write(self.style.ERROR(f"Skipping this batch due to an error: {e}"))
                    continue

                for q, result in zip(chunk, results):
                    total_checked += 1
                    if not result['in_syllabus']:
                        total_flagged += 1
                        self.stdout.write(self.style.WARNING(
                            f"  FLAGGED id={q.id}: {q.text[:80]}\n    reason: {result['reason']}"
                        ))
                        if auto_delete:
                            q.delete()
                            total_deleted += 1
                    last_id_seen = q.id

                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS("\nAudit complete."))
        self._summary(total_checked, total_flagged, total_deleted)

    def _summary(self, total_checked, total_flagged, total_deleted):
        self.stdout.write(self.style.SUCCESS(
            f"Checked {total_checked} question(s), flagged {total_flagged} as possibly off-syllabus"
            + (f", deleted {total_deleted}." if total_deleted else " (not deleted - re-run with --auto-delete to remove them).")
        ))
