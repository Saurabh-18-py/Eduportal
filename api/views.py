from .mathclean import clean_math
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile, Avatar, Message
from notes.models import Subject, Chapter, Note, PYQPaper
from mocktest.models import Test, Question, Choice, TestAttempt, StudentAnswer
from doubtsolver.models import DoubtMessage
from doubtsolver.doubt_ai import get_tutor_reply_with_rotation
from mocktest.ai_helpers import load_doubtsolver_api_keys, MCQGenerationError

from .serializers import (
    RegisterSerializer, StudentProfileSerializer, AvatarSerializer,
    SubjectSerializer, ChapterSerializer, NoteSerializer, PYQPaperSerializer,
    TestListSerializer, QuestionSerializer, SubmitAnswerSerializer, TestAttemptSerializer,
    DoubtMessageSerializer, AskDoubtSerializer,
    MessageSerializer, SendMessageSerializer,
    UpdateProfileSerializer, ChangePasswordSerializer,
)

DEFAULT_DOUBT_DAILY_LIMIT = 10
_doubt_key_index = [0]


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
                'explanation': clean_math(q.explanation),
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


# ------------------------------------------------------------- my results

class MyAttemptsView(generics.ListAPIView):
    """GET /api/attempts/ - the logged-in student's own test attempt history, newest first."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TestAttemptSerializer

    def get_queryset(self):
        return TestAttempt.objects.filter(student=self.request.user).select_related('test', 'test__subject').order_by('-started_at')


# ------------------------------------------------------------ doubt solver

class DoubtHistoryView(APIView):
    """GET /api/doubts/ - chat history + how many doubts are left today."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        history = DoubtMessage.objects.filter(student=request.user).order_by('created_at')
        profile = StudentProfile.objects.filter(user=request.user).first()
        limit = profile.doubt_limit_per_day if profile else DEFAULT_DOUBT_DAILY_LIMIT
        asked_today = DoubtMessage.objects.filter(
            student=request.user, role='user', created_at__date=timezone.localdate()
        ).count()
        return Response({
            'history': DoubtMessageSerializer(history, many=True).data,
            'doubts_left': max(limit - asked_today, 0),
            'doubt_limit': limit,
        })


class AskDoubtView(APIView):
    """POST /api/doubts/ask/ {"message": "..."} - ask the AI tutor a new doubt."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AskDoubtSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['message'].strip()
        if not question:
            return Response({'error': 'Type a doubt first.'}, status=400)

        profile = StudentProfile.objects.filter(user=request.user).first()
        limit = profile.doubt_limit_per_day if profile else DEFAULT_DOUBT_DAILY_LIMIT
        asked_today = DoubtMessage.objects.filter(
            student=request.user, role='user', created_at__date=timezone.localdate()
        ).count()
        if asked_today >= limit:
            return Response({
                'error': f"You've used all {limit} doubts for today. It resets at midnight.",
                'limit_reached': True,
            }, status=429)

        DoubtMessage.objects.create(student=request.user, role='user', content=question)

        recent = DoubtMessage.objects.filter(student=request.user).order_by('-created_at')[:12]
        history = [{'role': m.role, 'content': m.content} for m in reversed(recent)]

        api_keys = load_doubtsolver_api_keys()
        class_level = profile.class_level if profile else None
        try:
            reply = get_tutor_reply_with_rotation(api_keys, _doubt_key_index, class_level, history)
        except MCQGenerationError:
            reply = "Sorry, I couldn't reach the AI tutor just now. Please try again in a moment."

        DoubtMessage.objects.create(student=request.user, role='assistant', content=reply)
        return Response({'reply': reply})


# ---------------------------------------------------------------- messages

def _get_owner():
    from django.contrib.auth.models import User
    return User.objects.filter(is_superuser=True).order_by('id').first()


class InboxView(APIView):
    """GET /api/messages/ - the student's conversation thread with the site owner."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        owner = _get_owner()
        if not owner:
            return Response({'messages': []})
        thread = Message.objects.filter(
            sender__in=[request.user, owner], recipient__in=[request.user, owner]
        ).order_by('created_at')
        thread.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'messages': MessageSerializer(thread, many=True, context={'request': request}).data})


class SendMessageView(APIView):
    """POST /api/messages/send/ {"text": "..."} - message the site owner."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        owner = _get_owner()
        if not owner:
            return Response({'error': 'Messaging is not available right now.'}, status=503)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = Message.objects.create(sender=request.user, recipient=owner, text=serializer.validated_data['text'])
        return Response(MessageSerializer(msg, context={'request': request}).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- profile

class AvatarListView(generics.ListAPIView):
    """GET /api/avatars/ - the preset avatars a student can pick from."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvatarSerializer
    queryset = Avatar.objects.filter(is_active=True).order_by('order', 'id')

    def get_serializer_context(self):
        return {'request': self.request}


class UpdateProfileView(generics.UpdateAPIView):
    """PATCH /api/auth/me/update/ {"phone": "...", "avatar_id": 3} - update phone/avatar."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UpdateProfileSerializer

    def get_object(self):
        return get_object_or_404(StudentProfile, user=self.request.user)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ {"old_password": "...", "new_password": "..."}"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not check_password(serializer.validated_data['old_password'], user.password):
            return Response({'error': 'Current password is incorrect.'}, status=400)
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])
        return Response({'ok': True})
