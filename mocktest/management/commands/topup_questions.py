import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import (
    load_api_keys,
    generate_mcqs_batch_with_rotation,
    MCQGenerationError,
    RateLimitError,
)


class Command(BaseCommand):
    help = (
        "Top up every existing mock test toward a target question count, generating "
        "extra MCQs in small batches via Groq AI and appending them to each test's "
        "question bank. Safe to stop (Ctrl+C) and re-run any time - it always "
        "resumes from the first test that isn't at the target yet. Supports rotating "
        "across multiple Groq API keys (set GROQ_API_KEYS, comma-separated) and only "
        "stops once every configured key is out of quota. Just re-run the same "
        "command again later (e.g. once a day) to keep going."
    )

    def add_arguments(self, parser):
        parser.add_argument('--target', type=int, default=100, help='Target question count per test (default 100)')
        parser.add_argument('--batch-size', type=int, default=15, help='Questions requested per API call (default 15 - kept modest to fit under the 8000 tokens/minute cap)')
        parser.add_argument('--difficulty', default='hard', choices=['easy', 'medium', 'hard'], help='Question difficulty (default hard)')
        parser.add_argument('--class', dest='class_level', type=int, default=None, help='Limit to one class, e.g. 10 (default: all classes)')
        parser.add_argument('--subject', default=None, help='Limit to one subject name, e.g. "Science" (default: all subjects)')
        parser.add_argument('--delay', type=int, default=25, help='Seconds to wait between API calls (default 25 - tuned to stay under 8000 tokens/minute)')
        parser.add_argument(
            '--min-remaining-tokens', type=int, default=6000,
            help='Proactively switch to the next API key once fewer than this many tokens remain on the current one (default 6000)'
        )

    def handle(self, *args, **options):
        api_keys = load_api_keys()
        if not api_keys:
            raise CommandError(
                "No Groq API key found.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'\n"
                "Or, to rotate across multiple accounts once one hits its limit:\n"
                "  export GROQ_API_KEYS='key_one,key_two,key_three'\n"
            )
        if len(api_keys) > 1:
            self.stdout.write(f"Using {len(api_keys)} API keys, rotating as needed.")
        key_index = [0]

        target = options['target']
        batch_size = options['batch_size']
        difficulty = options['difficulty']
        delay = options['delay']
        min_remaining = options['min_remaining_tokens']

        tests = Test.objects.select_related('subject').order_by(
            'subject__class_level', 'subject__name', 'title'
        )
        if options['class_level']:
            tests = tests.filter(subject__class_level=options['class_level'])
        if options['subject']:
            tests = tests.filter(subject__name__iexact=options['subject'])

        total_added = 0
        tests_completed = 0
        tests_total = tests.count()

        def on_rotate(old_idx, new_idx):
            self.stdout.write(self.style.WARNING(
                f"  Key #{old_idx + 1}/{len(api_keys)} is rate-limited, switching to key #{new_idx + 1}..."
            ))

        for test in tests:
            current_count = test.questions.count()
            if current_count >= target:
                tests_completed += 1
                continue

            # "Heredity - Practice Test" -> "Heredity"
            topic = test.title.replace(' - Practice Test', '').strip()

            while current_count < target:
                remaining_needed = target - current_count
                this_batch = min(batch_size, remaining_needed)

                self.stdout.write(
                    f"[Class {test.subject.class_level} | {test.subject.name}] {topic}: "
                    f"{current_count}/{target} - requesting {this_batch} more..."
                )

                try:
                    questions_data, meta = generate_mcqs_batch_with_rotation(
                        api_keys, key_index, test.subject.name, topic, test.subject.class_level,
                        this_batch, difficulty, on_rotate=on_rotate,
                    )
                except RateLimitError as e:
                    self.stdout.write(self.style.WARNING(
                        f"\nAll {len(api_keys)} API key(s) are rate-limited. Stopping here for now.\n"
                        f"Re-run this exact same command later (e.g. tomorrow, or add another key "
                        f"to GROQ_API_KEYS) to continue - it will pick up right where it left off.\n({e})"
                    ))
                    self._summary(total_added, tests_completed, tests_total)
                    return
                except MCQGenerationError as e:
                    self.stdout.write(self.style.ERROR(
                        f"Skipping the rest of '{topic}' due to an error: {e}"
                    ))
                    break

                with transaction.atomic():
                    next_order = test.questions.count() + 1
                    for q in questions_data:
                        question = Question.objects.create(
                            test=test, text=q['question'], order=next_order
                        )
                        next_order += 1
                        for choice_text in q['options']:
                            Choice.objects.create(
                                question=question,
                                text=choice_text,
                                is_correct=(choice_text == q['correct_answer']),
                            )

                added = len(questions_data)
                total_added += added
                current_count = test.questions.count()

                remaining_tokens = meta.get('remaining_tokens')
                if remaining_tokens is not None and remaining_tokens < min_remaining and len(api_keys) > 1:
                    old_idx = key_index[0]
                    key_index[0] = (key_index[0] + 1) % len(api_keys)
                    self.stdout.write(
                        f"  Key #{old_idx + 1} is running low (~{remaining_tokens} tokens left) - "
                        f"proactively switching to key #{key_index[0] + 1} for the next batch."
                    )
                elif remaining_tokens is not None and remaining_tokens < min_remaining:
                    self.stdout.write(self.style.WARNING(
                        f"\nOnly ~{remaining_tokens} tokens left for today - stopping here "
                        f"before hitting the hard limit.\n"
                        f"Re-run this exact same command later (e.g. tomorrow) to continue."
                    ))
                    self._summary(total_added, tests_completed, tests_total)
                    return

                if current_count < target:
                    time.sleep(delay)

            if current_count >= target:
                tests_completed += 1

        self.stdout.write(self.style.SUCCESS("\nAll matching tests are at the target question count!"))
        self._summary(total_added, tests_completed, tests_total)

    def _summary(self, total_added, tests_completed, tests_total):
        self.stdout.write(self.style.SUCCESS(
            f"\nAdded {total_added} questions this run. "
            f"{tests_completed}/{tests_total} tests are now at (or above) the target."
        ))
