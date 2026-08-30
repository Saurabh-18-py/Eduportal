import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject
from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import generate_mcqs_via_groq, MCQGenerationError, RateLimitError

# CBSE Class 10 syllabus (2026-27, rationalised NCERT). Add more classes/subjects here later.
SYLLABUS = {
    10: {
        "Science": [
            "Chemical Reactions and Equations",
            "Acids, Bases and Salts",
            "Metals and Non-metals",
            "Carbon and its Compounds",
            "Life Processes",
            "Control and Coordination",
            "How do Organisms Reproduce",
            "Heredity",
            "Light - Reflection and Refraction",
            "The Human Eye and the Colourful World",
            "Electricity",
            "Magnetic Effects of Electric Current",
            "Our Environment",
        ],
        "Mathematics": [
            "Real Numbers",
            "Polynomials",
            "Pair of Linear Equations in Two Variables",
            "Quadratic Equations",
            "Arithmetic Progressions",
            "Triangles",
            "Coordinate Geometry",
            "Introduction to Trigonometry",
            "Some Applications of Trigonometry",
            "Circles",
            "Areas Related to Circles",
            "Surface Areas and Volumes",
            "Statistics",
            "Probability",
        ],
        "Social Science": [
            "The Rise of Nationalism in Europe",
            "Nationalism in India",
            "The Making of a Global World",
            "Print Culture and the Modern World",
            "Resources and Development",
            "Forest and Wildlife Resources",
            "Water Resources",
            "Agriculture",
            "Minerals and Energy Resources",
            "Lifelines of National Economy",
            "Power-sharing",
            "Federalism",
            "Gender, Religion and Caste",
            "Political Parties",
            "Outcomes of Democracy",
            "Development",
            "Sectors of the Indian Economy",
            "Money and Credit",
            "Globalisation and the Indian Economy",
        ],
    },
}


class Command(BaseCommand):
    help = "Bulk-generate PYQ-style MCQ tests for an entire class's syllabus (all subjects & chapters) using Groq AI."

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: currently 10 is available')
        parser.add_argument('--subject', default=None, help='Limit to one subject, e.g. "Science" (default: all subjects for the class)')
        parser.add_argument('--num', type=int, default=10, help='Number of MCQs per chapter (default 10)')
        parser.add_argument('--difficulty', default='hard', choices=['easy', 'medium', 'hard'], help='Question difficulty (default: hard)')
        parser.add_argument('--delay', type=int, default=20, help='Seconds to wait between chapters, to stay within free-tier rate limits (default 20)')
        parser.add_argument('--skip-existing', action='store_true', default=True, help='Skip chapters that already have a test with the same title (default: on)')

    def handle(self, *args, **options):
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise CommandError(
                "GROQ_API_KEY environment variable not set.\n"
                "In Termux, run:\n"
                "  export GROQ_API_KEY='your-key-here'\n"
            )

        class_level = options['class_level']
        subject_filter = options['subject']
        num_questions = options['num']
        difficulty = options['difficulty']
        delay = options['delay']

        if class_level not in SYLLABUS:
            raise CommandError(
                f"No syllabus data for Class {class_level} yet. Currently available: {list(SYLLABUS.keys())}.\n"
                "Ask to have this class's chapter list added."
            )

        subjects_map = SYLLABUS[class_level]
        if subject_filter:
            if subject_filter not in subjects_map:
                raise CommandError(f"Subject '{subject_filter}' not found for Class {class_level}. Available: {list(subjects_map.keys())}")
            subjects_map = {subject_filter: subjects_map[subject_filter]}

        total_chapters = sum(len(chapters) for chapters in subjects_map.values())
        self.stdout.write(f"Starting bulk generation: {total_chapters} chapters across {len(subjects_map)} subject(s) for Class {class_level}.")
        self.stdout.write(f"Difficulty: {difficulty} | Questions per chapter: {num_questions} | Delay between calls: {delay}s\n")

        done = 0
        failed = []
        skipped = 0

        for subject_name, chapters in subjects_map.items():
            subject, created = Subject.objects.get_or_create(
                name=subject_name,
                class_level=class_level,
                board='CBSE',
            )
            if created:
                self.stdout.write(self.style.WARNING(f"Created subject: {subject}"))

            for chapter in chapters:
                test_title = f"{chapter} - Practice Test"

                if Test.objects.filter(subject=subject, title=test_title).exists():
                    self.stdout.write(f"[skip] {subject_name} - {chapter} (already exists)")
                    skipped += 1
                    continue

                self.stdout.write(f"[{done + len(failed) + skipped + 1}/{total_chapters}] Generating: {subject_name} - {chapter} ...")

                questions_data = None
                max_retries = 4
                for attempt in range(1, max_retries + 1):
                    try:
                        questions_data = generate_mcqs_via_groq(
                            api_key, subject_name, chapter, class_level, num_questions, difficulty
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
                        failed.append(f"{subject_name} - {chapter}")
                        break

                if questions_data is None:
                    if f"{subject_name} - {chapter}" not in failed:
                        self.stdout.write(self.style.ERROR(f"    FAILED after {max_retries} retries (rate limit)."))
                        failed.append(f"{subject_name} - {chapter}")
                    time.sleep(delay)
                    continue

                try:
                    with transaction.atomic():
                        test = Test.objects.create(
                            title=test_title,
                            subject=subject,
                            duration_minutes=max(15, num_questions * 2),
                        )
                        for i, q in enumerate(questions_data, start=1):
                            question = Question.objects.create(test=test, text=q['question'], order=i)
                            for choice_text in q['options']:
                                Choice.objects.create(
                                    question=question,
                                    text=choice_text,
                                    is_correct=(choice_text == q['correct_answer']),
                                )
                    self.stdout.write(self.style.SUCCESS(f"    done - {len(questions_data)} questions saved."))
                    done += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    FAILED to save: {e}"))
                    failed.append(f"{subject_name} - {chapter}")

                time.sleep(delay)

        self.stdout.write("\n" + self.style.SUCCESS(f"Finished. Created: {done}, Skipped (already existed): {skipped}, Failed: {len(failed)}"))
        if failed:
            self.stdout.write(self.style.ERROR("Failed chapters (re-run generate_mcqs manually for these):"))
            for f in failed:
                self.stdout.write(f"  - {f}")
