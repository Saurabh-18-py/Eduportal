import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject
from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import generate_mcqs_via_groq, MCQGenerationError


class Command(BaseCommand):
    help = "Auto-generate PYQ-style MCQ mock test questions for ONE chapter using Groq AI (free) and save them to the database."

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Subject name, e.g. "Science"')
        parser.add_argument('--chapter', required=True, help='Chapter/topic name, e.g. "Chemical Reactions and Equations"')
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: 9, 10, 11 or 12')
        parser.add_argument('--num', type=int, default=10, help='Number of MCQs to generate (default 10)')
        parser.add_argument('--difficulty', default='medium', choices=['easy', 'medium', 'hard'], help='Question difficulty (default: medium)')
        parser.add_argument('--test-title', default=None, help='Title for the generated test (default: "<chapter> Practice Test")')

    def handle(self, *args, **options):
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise CommandError(
                "GROQ_API_KEY environment variable not set.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'\n"
                "(add this line to your ~/.bashrc so you don't have to repeat it every session)"
            )

        subject_name = options['subject']
        chapter = options['chapter']
        class_level = options['class_level']
        num_questions = options['num']
        difficulty = options['difficulty']
        test_title = options['test_title'] or f"{chapter} - Practice Test"

        subject, created = Subject.objects.get_or_create(
            name=subject_name,
            class_level=class_level,
            board='CBSE',
        )
        if created:
            self.stdout.write(self.style.WARNING(f"Created new subject: {subject}"))

        self.stdout.write(f"Asking Groq AI to generate {num_questions} {difficulty} MCQs on '{chapter}' (Class {class_level} {subject_name})...")

        try:
            questions_data = generate_mcqs_via_groq(api_key, subject_name, chapter, class_level, num_questions, difficulty)
        except MCQGenerationError as e:
            raise CommandError(str(e))

        with transaction.atomic():
            test = Test.objects.create(
                title=test_title,
                subject=subject,
                duration_minutes=max(15, num_questions * 2),
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
            f"Done! Created test '{test.title}' with {len(questions_data)} questions under {subject}."
        ))
