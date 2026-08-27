import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject
from mocktest.models import Test, Question, Choice


class Command(BaseCommand):
    help = (
        "Import MCQ questions from a JSON file (copied from Claude/ChatGPT) into a new mock Test.\n"
        "JSON format expected:\n"
        "[\n"
        '  {"question": "...", "options": ["A", "B", "C", "D"], "correct_answer": "B"},\n'
        "  ...\n"
        "]"
    )

    def add_arguments(self, parser):
        parser.add_argument('json_file', help='Path to the JSON file containing questions')
        parser.add_argument('--subject', required=True, help='Subject name, e.g. "Science"')
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: 9, 10, 11 or 12')
        parser.add_argument('--test-title', required=True, help='Title for the test, e.g. "Chemical Reactions Practice Test"')
        parser.add_argument('--duration', type=int, default=None, help='Test duration in minutes (default: 2 min per question)')

    def handle(self, *args, **options):
        json_path = options['json_file']
        subject_name = options['subject']
        class_level = options['class_level']
        test_title = options['test_title']

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = f.read()
        except FileNotFoundError:
            raise CommandError(f"File not found: {json_path}")

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            questions_data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(
                f"Could not parse {json_path} as JSON: {e}\n"
                "Make sure the file contains ONLY the JSON array — no extra text before or after it."
            )

        if not isinstance(questions_data, list) or not questions_data:
            raise CommandError("JSON file must contain a non-empty list of questions.")

        for i, q in enumerate(questions_data, start=1):
            if 'question' not in q or 'options' not in q or 'correct_answer' not in q:
                raise CommandError(f"Question #{i} is missing 'question', 'options' or 'correct_answer' field: {q}")
            if len(q['options']) != 4:
                raise CommandError(f"Question #{i} must have exactly 4 options, found {len(q['options'])}: {q}")
            if q['correct_answer'] not in q['options']:
                raise CommandError(
                    f"Question #{i}: correct_answer '{q['correct_answer']}' does not exactly match any option in {q['options']}"
                )

        subject, created = Subject.objects.get_or_create(
            name=subject_name,
            class_level=class_level,
            board='CBSE',
        )
        if created:
            self.stdout.write(self.style.WARNING(f"Created new subject: {subject}"))

        duration = options['duration'] or max(15, len(questions_data) * 2)

        with transaction.atomic():
            test = Test.objects.create(
                title=test_title,
                subject=subject,
                duration_minutes=duration,
            )
            for i, q in enumerate(questions_data, start=1):
                question = Question.objects.create(
                    test=test,
                    text=q['question'],
                    order=i,
                )
                for choice_text in q['options']:
                    Choice.objects.create(
                        question=question,
                        text=choice_text,
                        is_correct=(choice_text == q['correct_answer']),
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(questions_data)} questions into test '{test.title}' under {subject}."
        ))
