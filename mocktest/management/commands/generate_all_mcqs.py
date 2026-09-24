import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from notes.models import Subject
from notes.new_subjects_syllabus import NEW_SUBJECTS_SYLLABUS
from mocktest.models import Test, Question, Choice
from mocktest.ai_helpers import (
    generate_mcqs_via_groq, MCQGenerationError, RateLimitError,
    InvalidAPIKeyError, load_api_keys,
)

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
    11: {
        "History": [
            "From the Beginning of Time",
            "Writing and City Life",
            "An Empire Across Three Continents",
            "The Central Islamic Lands",
            "Nomadic Empires",
            "The Three Orders",
            "Changing Cultural Traditions",
            "Confrontation of Cultures",
            "The Industrial Revolution",
            "Displacing Indigenous Peoples",
            "Paths to Modernization",
        ],
        "Political Science": [
            "Constitution: Why and How?",
            "Rights in the Indian Constitution",
            "Election and Representation",
            "Executive",
            "Legislature",
            "Judiciary",
            "Federalism",
            "Local Governments",
            "Constitution as a Living Document",
            "The Philosophy of the Constitution",
            "Political Theory: An Introduction",
            "Freedom",
            "Equality",
            "Social Justice",
            "Rights",
            "Citizenship",
            "Nationalism",
            "Secularism",
            "Peace",
            "Development",
        ],
        "Geography": [
            "Geography as a Discipline",
            "The Origin and Evolution of the Earth",
            "Interior of the Earth",
            "Distribution of Oceans and Continents",
            "Minerals and Rocks",
            "Geomorphic Processes",
            "Landforms and their Evolution",
            "Composition and Structure of Atmosphere",
            "Solar Radiation, Heat Balance and Temperature",
            "Atmospheric Circulation and Weather Systems",
            "Water in the Atmosphere",
            "World Climate and Climate Change",
            "Water (Oceans)",
            "Movements of Ocean Water",
            "Life on the Earth",
            "Biodiversity and Conservation",
            "India - Location",
            "Structure and Physiography",
            "Drainage System",
            "Climate",
            "Natural Vegetation",
            "Soils",
            "Natural Hazards and Disasters",
        ],
        "Sociology": [
            "Sociology and Society",
            "Terms, Concepts and Their Use in Sociology",
            "Understanding Social Institutions",
            "Culture and Socialisation",
            "Doing Sociology: Research Methods",
            "Social Structure, Stratification and Social Processes in Society",
            "Social Change and Social Order in Rural and Urban Society",
            "Environment and Society",
            "Introducing Western Sociologists",
            "Indian Sociologists",
        ],
        "Psychology": [
            "What is Psychology?",
            "Methods of Enquiry in Psychology",
            "The Bases of Human Behaviour",
            "Human Development",
            "Sensory, Attentional and Perceptual Processes",
            "Learning",
            "Human Memory",
            "Thinking",
            "Motivation and Emotion",
        ],
        "Physics": [
            "Units and Measurements",
            "Motion in a Straight Line",
            "Motion in a Plane",
            "Laws of Motion",
            "System of Particles and Rotational Motion",
            "Gravitation",
            "Mechanical Properties of Solids",
            "Mechanical Properties of Fluids",
            "Thermal Properties of Matter",
            "Thermodynamics",
            "Kinetic Theory",
            "Oscillations",
            "Waves",
            "Work Energy and Power",
        ],
        "Chemistry": [
            "Some Basic Concepts of Chemistry",
            "Structure of Atom",
            "Classification of Elements and Periodicity in Properties",
            "Chemical Bonding and Molecular Structure",
            "Thermodynamics",
            "Equilibrium",
            "Redox Reactions",
            "Organic Chemistry  Some Basic Principles and Techniques",
            "Hydrocarbons",
        ],
        "Biology": [
            "The Living World",
            "Biological Classification",
            "Plant Kingdom",
            "Animal Kingdom",
            "Morphology of Flowering Plants",
            "Anatomy of Flowering Plants",
            "Structural Organisation in Animals Frog",
            "Cell The Unit of Life",
            "Biomolecules",
            "Cell Cycle and Cell Division",
            "Photosynthesis in Higher Plants",
            "Respiration in Plants",
            "Plant Growth and Development",
            "Breathing and Exchange of Gases",
            "Body Fluids and Circulation",
            "Excretory Products and their Elimination",
            "Locomotion and Movement",
            "Neural Control and Coordination",
            "Chemical Coordination and Integration",
        ],
        "Accountancy": [
            "Introduction to Accounting",
            "Basic Accounting Terms",
            "Theory Base of Accounting",
            "Recording of Transactions-I",
            "Recording of Transactions-II",
            "Bank Reconciliation Statement",
            "Depreciation, Provisions and Reserves",
            "Trial Balance and Rectification of Errors",
            "Financial Statements-I",
            "Financial Statements-II",
            "Accounts from Incomplete Records",
        ],
        "Business Studies": [
            "Business, Trade and Commerce",
            "Forms of Business Organisation",
            "Private, Public and Global Enterprises",
            "Business Services",
            "Emerging Modes of Business",
            "Social Responsibility of Business and Business Ethics",
            "Formation of a Company",
            "Sources of Business Finance",
            "Small Business",
            "Internal Trade",
            "International Business",
        ],
        "Economics": [
            "Introduction",
            "Collection of Data",
            "Organisation of Data",
            "Presentation of Data",
            "Measures of Central Tendency",
            "Measures of Dispersion",
            "Correlation",
            "Index Numbers",
            "Use of Statistical Tools",
            "Indian Economy on the Eve of Independence",
            "Indian Economy 1950-1990",
            "Liberalisation, Privatisation and Globalisation: An Appraisal",
            "Poverty",
            "Human Capital Formation in India",
            "Rural Development",
            "Employment Growth, Informalisation and Other Issues",
            "Infrastructure",
            "Environment and Sustainable Development",
            "Comparative Development Experiences of India and its Neighbours",
        ],
        "Mathematics": [
            "Sets",
            "Relations and Functions",
            "Trigonometric Functions",
            "Complex Numbers and Quadratic Equations",
            "Linear Inequalities",
            "Permutations and Combinations",
            "Binomial Theorem",
            "Sequences and Series",
            "Straight Lines",
            "Conic Sections",
            "Introduction to Three Dimensional Geometry",
            "Limits and Derivatives",
            "Statistics",
            "Probability",
        ],
    },
}

# Merge in the newer subjects (Hindi, English, Grammar, Vyakaran, IT) for
# every class - including Class 9 and 12, which had no syllabus data here
# before.
for _class_level, _subjects in NEW_SUBJECTS_SYLLABUS.items():
    SYLLABUS.setdefault(_class_level, {})
    for _subject_name, _chapters in _subjects.items():
        SYLLABUS[_class_level].setdefault(_subject_name, _chapters)


class Command(BaseCommand):
    help = (
        "Create Test 'shells' (Subject + one Test per chapter, 0 questions) for an "
        "entire class's syllabus, WITHOUT calling the AI - this is instant and never "
        "hits Groq's rate limits. After running this, use 'topup_questions' to "
        "actually fill each test with questions in small, safe batches."
    )

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='class_level', type=int, required=True, help='Class level: 9, 10, 11 or 12')
        parser.add_argument('--subject', default=None, help='Limit to one subject, e.g. "Science" (default: all subjects for the class)')
        parser.add_argument('--duration', type=int, default=None, help='Duration in minutes to set on each new test (default: 100 minutes, since tests are meant to grow to ~100 questions)')

    def handle(self, *args, **options):
        class_level = options['class_level']
        subject_filter = options['subject']
        duration = options['duration'] or 100

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
        self.stdout.write(f"Setting up {total_chapters} test(s) across {len(subjects_map)} subject(s) for Class {class_level} (no AI calls, instant).\n")

        created_count = 0
        skipped_count = 0

        for subject_name, chapters in subjects_map.items():
            subject, subject_created = Subject.objects.get_or_create(
                name=subject_name,
                class_level=class_level,
                board='CBSE',
            )
            if subject_created:
                self.stdout.write(self.style.WARNING(f"Created subject: {subject}"))

            for chapter in chapters:
                test_title = f"{chapter} - Practice Test"
                test, test_created = Test.objects.get_or_create(
                    subject=subject,
                    title=test_title,
                    defaults={'duration_minutes': duration},
                )
                if test_created:
                    created_count += 1
                    self.stdout.write(f"[created] {subject_name} - {chapter}")
                else:
                    skipped_count += 1
                    self.stdout.write(f"[exists]  {subject_name} - {chapter} ({test.questions.count()} questions so far)")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Tests created: {created_count}, already existed: {skipped_count}.\n"
            f"Next step - actually generate the questions (safe small batches, resumable):\n"
            f"  python manage.py topup_questions --class {class_level}"
            + (f" --subject \"{subject_filter}\"" if subject_filter else "")
            + " --target 100"
        ))
