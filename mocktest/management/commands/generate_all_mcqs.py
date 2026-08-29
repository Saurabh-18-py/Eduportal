import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject
from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import generate_mcqs_via_groq, MCQGenerationError, RateLimitError

# CBSE Class 10 syllabus (2026-27, rationalised NCERT). Add more classes/subjects here later.
SYLLABUS = {
    9: {
        "Mathematics": [
            "Orienting Yourself: The Use of Coordinates",
            "Introduction to Linear Polynomials",
            "The World of Numbers",
            "Exploring Algebraic Identities",
            "I'm Up and Down, and Round and Round",
            "Measuring Space: Perimeter and Area",
            "The Mathematics of Maybe: Introduction to Probability",
            "Predicting What Comes Next: Exploring Sequences and Progressions",
        ],
        "Science": [
            "Exploration: Entering the World of Secondary Science",
            "Cell: The Building Block of Life",
            "Tissues in Action",
            "Describing Motion Around Us",
            "Exploring Mixtures and Their Separation",
            "How Forces Affect Motion",
            "Work, Energy, and Simple Machines",
            "Journey Inside the Atom",
            "Atomic Foundations of Matter",
            "Sound Waves: Characteristics and Applications",
            "Reproduction: How Life Continues",
            "Patterns in Life: Diversity and Classification",
            "Earth as a System: Energy, Matter, and Life",
        ],
        "Social Science": [
            "Social Science: Meaning, Scope, and Importance",
            "Landforms: Earth's Living Canvas",
            "The Dynamic Atmosphere and Changing Climate",
            "The Earliest People: The Stone Age",
            "Harappan and Mesopotamian Civilisation",
            "Egyptian and Chinese Civilisations",
            "Vedic Age",
            "Rise of Kingdoms, Republics and Early Empires",
            "Understanding Democracy",
            "Elections in a Democracy",
            "Why Choices Matter: The Basics of Economics",
            "Why Prices Change: Demand and Supply",
            "Water in the Oceans",
            "Disaster Preparedness and Regulatory Frameworks",
            "Forests, Biodiversity and Livelihoods",
            "Conservation and Livelihoods in Forest Areas",
            "Early Medieval India",
            "Later Medieval India",
            "Ancient India",
            "India from 750 CE to 1200 CE",
            "The Idea of Authority",
            "Entrepreneurship and Startups",
            "Financial Planning, Investment and Taxation",
        ],
    },
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
    12: {
        "Accountancy": [
            "Accounting for Partnership - Basic Concepts",
            "Reconstitution of Partnership - Admission of a Partner",
            "Reconstitution of Partnership - Retirement/Death of a Partner",
            "Dissolution of Partnership Firm",
            "Accounting for Share Capital",
            "Issue and Redemption of Debentures",
            "Financial Statements of a Company",
            "Analysis of Financial Statements",
            "Accounting Ratios",
            "Cash Flow Statement",
        ],
        "Business Studies": [
            "Nature and Significance of Management",
            "Principles of Management",
            "Business Environment",
            "Planning",
            "Organising",
            "Staffing",
            "Directing",
            "Controlling",
            "Financial Management",
            "Financial Markets",
            "Marketing Management",
            "Consumer Protection",
        ],
        "Economics": [
            "National Income Accounting",
            "Money and Banking",
            "Determination of Income and Employment",
            "Government Budget and the Economy",
            "Balance of Payments",
            "Development Experience of India",
            "Indian Economy on the Eve of Independence",
            "Indian Economy 1950-1990",
            "Liberalisation, Privatisation and Globalisation",
            "Poverty",
            "Human Capital Formation in India",
            "Rural Development",
            "Employment - Growth, Informalisation and Related Issues",
            "Infrastructure",
            "Environment and Sustainable Development",
        ],
        "History": [
            "Bricks, Beads and Bones - The Harappan Civilisation",
            "Kings, Farmers and Towns - Early States and Economies",
            "Kinship, Caste and Class - Early Societies",
            "Thinkers, Beliefs and Buildings - Cultural Developments",
            "Through the Eyes of Travellers - Perceptions of Society",
            "Bhakti-Sufi Traditions - Changes in Religious Beliefs",
            "An Imperial Capital - Vijayanagara",
            "Peasants, Zamindars and the State - Agrarian Society (Mughal Era)",
            "Kings and Chronicles - The Mughal Courts",
            "Colonialism and the Countryside",
            "Rebels and the Raj - 1857 Revolt",
            "Colonial Cities - Urbanisation, Planning and Architecture",
            "Mahatma Gandhi and the Nationalist Movement",
            "Understanding Partition",
            "Framing the Constitution",
        ],
        "Political Science": [
            "The Cold War Era",
            "The End of Bipolarity",
            "US Hegemony in World Politics",
            "Alternative Centres of Power",
            "Contemporary South Asia",
            "International Organisations",
            "Security in the Contemporary World",
            "Environment and Natural Resources",
            "Globalisation",
            "Challenges of Nation Building",
            "Era of One-Party Dominance",
            "Politics of Planned Development",
            "India's External Relations",
            "Challenges to and Restoration of the Congress System",
            "The Crisis of Democratic Order",
            "Rise of Popular Movements",
            "Regional Aspirations",
            "Recent Developments in Indian Politics",
        ],
        "Geography": [
            "Human Geography - Nature and Scope",
            "The World Population - Distribution, Density and Growth",
            "Population Composition",
            "Human Development",
            "Primary Activities",
            "Secondary Activities",
            "Tertiary and Quaternary Activities",
            "Transport and Communication",
            "International Trade",
            "Human Settlements",
            "Population - Distribution, Density, Growth (India)",
            "Migration - Types, Causes and Consequences",
            "Human Development (India)",
            "Human Settlements (India)",
            "Land Resources and Agriculture",
            "Water Resources",
            "Mineral and Energy Resources",
            "Manufacturing Industries",
            "Planning and Sustainable Development in Indian Context",
            "Transport and Communication (India)",
            "International Trade (India)",
            "Geographical Perspective on Selected Issues and Problems",
        ],
        "Psychology": [
            "Variations in Psychological Attributes",
            "Self and Personality",
            "Meeting Life Challenges",
            "Psychological Disorders",
            "Therapeutic Approaches",
            "Attitude and Social Cognition",
            "Social Influence and Group Processes",
            "Psychology and Life",
            "Developing Psychological Skills",
        ],
        "Physics": [
            "Electric Charges and Fields",
            "Electrostatic Potential and Capacitance",
            "Current Electricity",
            "Moving Charges and Magnetism",
            "Magnetism and Matter",
            "Electromagnetic Induction",
            "Alternating Current",
            "Electromagnetic Waves",
            "Ray Optics and Optical Instruments",
            "Wave Optics",
            "Dual Nature of Radiation and Matter",
            "Atoms",
            "Nuclei",
            "Semiconductor Electronics",
        ],
        "Chemistry": [
            "Solutions",
            "Electrochemistry",
            "Chemical Kinetics",
            "d and f Block Elements",
            "Coordination Compounds",
            "Haloalkanes and Haloarenes",
            "Alcohols, Phenols and Ethers",
            "Aldehydes, Ketones and Carboxylic Acids",
            "Amines",
            "Biomolecules",
        ],
        "Mathematics": [
            "Relations and Functions",
            "Inverse Trigonometric Functions",
            "Matrices",
            "Determinants",
            "Continuity and Differentiability",
            "Application of Derivatives",
            "Integrals",
            "Application of Integrals",
            "Differential Equations",
            "Vector Algebra",
            "Three Dimensional Geometry",
            "Linear Programming",
            "Probability",
        ],
        "Biology": [
            "Reproduction in Organisms",
            "Sexual Reproduction in Flowering Plants",
            "Human Reproduction",
            "Reproductive Health",
            "Principles of Inheritance and Variation",
            "Molecular Basis of Inheritance",
            "Evolution",
            "Human Health and Disease",
            "Microbes in Human Welfare",
            "Biotechnology - Principles and Processes",
            "Biotechnology and its Applications",
            "Organisms and Populations",
            "Ecosystem",
            "Biodiversity and Conservation",
        ],
    },
}


class Command(BaseCommand):
    help = "Bulk-generate PYQ-style MCQ tests for an entire class's syllabus (all subjects & chapters) using Groq AI."

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: currently 10 and 12 are available')
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
