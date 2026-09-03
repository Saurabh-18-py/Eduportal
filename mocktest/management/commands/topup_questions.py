import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import (
    generate_mcqs_batch_with_meta,
    MCQGenerationError,
    RateLimitError,
)


class Command(BaseCommand):
    help = (
        "Top up every existing mock test toward a target question count, generating "
        "extra MCQs in small batches via Groq AI and appending them to each test's "
        "question bank. Safe to stop (Ctrl+C) and re-run any time - it always "
        "resumes from the first test that isn't at the target yet, and stops itself "
        "gracefully once today's Groq quota is nearly used up. Just re-run the same "
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
            help='Stop the run once fewer than this many tokens remain for today (default 6000 - enough headroom for one more batch)'
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise CommandError(
                "GROQ_API_KEY environment variable not set.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'\n"
            )

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
                    questions_data, meta = generate_mcqs_batch_with_meta(
                        api_key, test.subject.name, topic, test.subject.class_level,
                        this_batch, difficulty,
                    )
                except RateLimitError as e:
                    self.stdout.write(self.style.WARNING(
                        f"\nRate limited by Groq. Stopping here for now.\n"
                        f"Re-run this exact same command later (e.g. tomorrow) to continue "
                        f"- it will pick up right where it left off.\n({e})"
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
                if remaining_tokens is not None and remaining_tokens < min_remaining:
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
