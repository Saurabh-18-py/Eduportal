from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from mocktest.models import TestAttempt

from .mathclean import clean_math
from .report import build_report


class AttemptDetailView(APIView):
    """GET /api/attempts/<id>/ - full result of one finished test (own attempts only; admin can see all)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = (
            TestAttempt.objects.select_related('test', 'test__subject')
            .filter(id=attempt_id).first()
        )
        if not attempt or (attempt.student_id != request.user.id and not request.user.is_superuser):
            return Response({'detail': 'Not found.'}, status=404)

        answers = list(
            attempt.answers.select_related('question', 'selected_choice')
            .prefetch_related('question__choices')
            .order_by('question__order', 'question__id')
        )
        questions, results = [], []
        for a in answers:
            q = a.question
            choices = list(q.choices.all())
            correct = next((c for c in choices if c.is_correct), None)
            questions.append({
                'id': q.id,
                'text': clean_math(q.text),
                'choices': [{'id': c.id, 'text': clean_math(c.text)} for c in choices],
            })
            results.append({
                'question_id': q.id,
                'your_choice_id': a.selected_choice_id,
                'correct_choice_id': correct.id if correct else None,
                'is_correct': bool(a.selected_choice and a.selected_choice.is_correct),
                'explanation': clean_math(q.explanation),
            })

        return Response({
            'attempt_id': attempt.id,
            'score': attempt.score,
            'total': attempt.total,
            'results': results,
            'questions': questions,
            'report': build_report(attempt),
            'test': {
                'id': attempt.test_id,
                'title': attempt.test.title,
                'subject': attempt.test.subject.name,
                'slice': attempt.slice_number,
            },
        })
