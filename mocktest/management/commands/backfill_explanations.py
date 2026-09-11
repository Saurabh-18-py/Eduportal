import time

from django.core.management.base import BaseCommand, CommandError

from mocktest.models import Question
from mocktest.ai_helpers import (
    load_api_keys,
    generate_explanations_batch_with_rotation,
    MCQGenerationError,
    RateLimitError,
    InvalidAPIKeyError,
)


class Command(BaseCommand):
    help = (
        "Backfills an explanation for every existing question that doesn't have one yet "
        "(older questions, generated before explanations were added). Safe to stop and "
        "re-run any time - always picks up questions still missing an explanation, and "
        "stops gracefully when every configured Groq key is out of quota."
    )

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=15, help='Questions per API call (default 15)')
        parser.add_argument('--delay', type=int, default=15, help='Seconds between API calls (default 15)')
        parser.add_argument('--class', dest='class_levels', type=int, nargs='+', default=None, help='Limit to one or more classes (default: all)')
        parser.add_argument('--subject', default=None, help='Limit to one subject name (default: all)')

    def handle(self, *args, **options):
        api_keys = load_api_keys()
        if not api_keys:
            raise CommandError("No Groq API key found. Set GROQ_API_KEY or GROQ_API_KEYS.")
        key_index = [0]

        batch_size = options['batch_size']
        delay = options['delay']

        questions = Question.objects.filter(explanation='').select_related('test__subject').prefetch_related('choices')
        if options['class_levels']:
            questions = questions.filter(test__subject__class_level__in=options['class_levels'])
        if options['subject']:
            questions = questions.filter(test__subject__name__iexact=options['subject'])
        questions = list(questions.order_by('id'))

        total = len(questions)
        self.stdout.write(f"{total} question(s) still need an explanation.")

        def on_rotate(old_idx, new_idx):
            self.stdout.write(self.style.WARNING(
                f"  Key #{old_idx + 1}/{len(api_keys)} is rate-limited, switching to key #{new_idx + 1}..."
            ))

        done = 0
        for i in range(0, total, batch_size):
            chunk = questions[i:i + batch_size]

            items = []
            for q in chunk:
                correct = next((c.text for c in q.choices.all() if c.is_correct), None)
                if correct is None:
                    continue
                items.append({'question_obj': q, 'question': q.text, 'correct_answer': correct})

            if not items:
                continue

            self.stdout.write(f"Explaining questions {chunk[0].id}-{chunk[-1].id} ({len(items)})...")

            try:
                explanations, meta = generate_explanations_batch_with_rotation(
                    api_keys, key_index,
                    [{'question': it['question'], 'correct_answer': it['correct_answer']} for it in items],
                    on_rotate=on_rotate,
                )
            except (RateLimitError, InvalidAPIKeyError) as e:
                self.stdout.write(self.style.WARNING(
                    f"\nAll {len(api_keys)} API key(s) are unusable right now. Stopping here.\n"
                    f"Re-run the same command later to continue - it'll pick up remaining questions.\n({e})"
                ))
                self._summary(done, total)
                return
            except MCQGenerationError as e:
                self.stdout.write(self.style.ERROR(f"Skipping this batch due to an error: {e}"))
                continue

            for item, explanation in zip(items, explanations):
                if explanation:
                    item['question_obj'].explanation = explanation
                    item['question_obj'].save(update_fields=['explanation'])
                    done += 1

            time.sleep(delay)

        self.stdout.write(self.style.SUCCESS("\nDone with this run."))
        self._summary(done, total)

    def _summary(self, done, total):
        self.stdout.write(self.style.SUCCESS(f"Added explanations to {done}/{total} question(s) this run."))
