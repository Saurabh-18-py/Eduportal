from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile
from notes.models import Subject, Chapter, Note, PYQPaper
from mocktest.models import Test, Question, Choice, TestAttempt, StudentAnswer

from .serializers import (
    RegisterSerializer, StudentProfileSerializer,
    SubjectSerializer, ChapterSerializer, NoteSerializer, PYQPaperSerializer,
    TestListSerializer, QuestionSerializer, SubmitAnswerSerializer,
)


# ---------------------------------------------------------------- accounts

class RegisterView(generics.CreateAPIView):
    """POST username, email, password, class_level -> creates account + student profile."""
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


class MeView(generics.RetrieveAPIView):
    """GET the logged-in student's own profile (needs a valid JWT access token)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudentProfileSerializer

    def get_object(self):
        return get_object_or_404(StudentProfile, user=self.request.user)


# ------------------------------------------------------------------- notes

class SubjectListView(generics.ListAPIView):
    """GET /api/subjects/?class_level=9 - subjects for a class (defaults to the logged-in student's own class)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SubjectSerializer

    def get_queryset(self):
        class_level = self.request.query_params.get('class_level')
        if not class_level:
            profile = StudentProfile.objects.filter(user=self.request.user).first()
            class_level = profile.class_level if profile else None
        qs = Subject.objects.all()
        if class_level:
            qs = qs.filter(class_level=class_level)
        return qs


class ChapterListView(generics.ListAPIView):
    """GET /api/subjects/<subject_id>/chapters/ - chapters for one subject, in order."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChapterSerializer

    def get_queryset(self):
        return Chapter.objects.filter(subject_id=self.kwargs['subject_id']).order_by('order', 'id')


class ChapterNotesView(generics.ListAPIView):
    """GET /api/chapters/<chapter_id>/notes/ - PDFs (notes + subjective questions) for one chapter."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NoteSerializer

    def get_queryset(self):
        return Note.objects.filter(chapter_id=self.kwargs['chapter_id'])


class PYQListView(generics.ListAPIView):
    """GET /api/pyq/?class_level=9&subject=Hindi - previous year papers, filterable."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PYQPaperSerializer

    def get_queryset(self):
        qs = PYQPaper.objects.select_related('subject').all()
        class_level = self.request.query_params.get('class_level')
        subject = self.request.query_params.get('subject')
        year = self.request.query_params.get('year')
        if class_level:
            qs = qs.filter(class_level=class_level)
        if subject:
            qs = qs.filter(subject__name__iexact=subject)
        if year:
            qs = qs.filter(year=year)
        return qs


# ---------------------------------------------------------------- mocktest

class TestListView(generics.ListAPIView):
    """GET /api/subjects/<subject_id>/tests/ - one row per chapter's question bank."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TestListSerializer

    def get_queryset(self):
        return Test.objects.filter(subject_id=self.kwargs['subject_id'])


class TestSliceView(APIView):
    """
    GET /api/tests/<test_id>/slice/<slice_number>/
    Returns the fixed 10 questions for that slice ("Test <slice_number>"),
    with choices but WITHOUT which one is correct.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, test_id, slice_number):
        test = get_object_or_404(Test, id=test_id)
        questions = test.get_slice_questions(int(slice_number))
        if not questions:
            return Response({'detail': 'No questions in this slice.'}, status=status.HTTP_404_NOT_FOUND)
        data = QuestionSerializer(questions, many=True).data
        return Response({
            'test_id': test.id,
            'test_title': test.title,
            'slice_number': int(slice_number),
            'duration_minutes': test.duration_minutes,
            'questions': data,
        })


class TestSliceSubmitView(APIView):
    """
    POST /api/tests/<test_id>/slice/<slice_number>/submit/
    Body: {"answers": [{"question_id": 1, "choice_id": 5}, ...]}
    Scores the attempt, saves it, and returns per-question correctness +
    explanations (only revealed now, after submission).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, test_id, slice_number):
        test = get_object_or_404(Test, id=test_id)
        questions = test.get_slice_questions(int(slice_number))
        if not questions:
            return Response({'detail': 'No questions in this slice.'}, status=status.HTTP_404_NOT_FOUND)

        answers_serializer = SubmitAnswerSerializer(data=request.data.get('answers', []), many=True)
        answers_serializer.is_valid(raise_exception=True)
        submitted = {a['question_id']: a['choice_id'] for a in answers_serializer.validated_data}

        attempt = TestAttempt.objects.create(student=request.user, test=test, total=len(questions))
        score = 0
        results = []

        for q in questions:
            selected_choice_id = submitted.get(q.id)
            selected_choice = None
            if selected_choice_id:
                selected_choice = next((c for c in q.choices.all() if c.id == selected_choice_id), None)
            StudentAnswer.objects.create(attempt=attempt, question=q, selected_choice=selected_choice)

            correct_choice = next((c for c in q.choices.all() if c.is_correct), None)
            is_correct = bool(selected_choice and selected_choice.is_correct)
            if is_correct:
                score += 1

            results.append({
                'question_id': q.id,
                'your_choice_id': selected_choice_id,
                'correct_choice_id': correct_choice.id if correct_choice else None,
                'is_correct': is_correct,
                'explanation': q.explanation,
            })

        from django.utils import timezone
        attempt.score = score
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['score', 'submitted_at'])

        return Response({
            'attempt_id': attempt.id,
            'score': score,
            'total': len(questions),
            'results': results,
        })
