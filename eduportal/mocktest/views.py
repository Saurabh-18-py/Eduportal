from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages

from notes.models import Subject
from .models import Test, TestAttempt, StudentAnswer, Choice


def test_list_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    tests = subject.tests.all()
    return render(request, 'mocktest/test_list.html', {
        'subject': subject,
        'tests': tests,
    })


@login_required
def take_test_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    questions = test.questions.prefetch_related('choices').all()

    if request.method == 'POST':
        attempt = TestAttempt.objects.create(
            student=request.user,
            test=test,
            submitted_at=timezone.now(),
            total=questions.count(),
        )

        score = 0
        for question in questions:
            selected_id = request.POST.get(f'question_{question.id}')
            selected_choice = None
            if selected_id:
                selected_choice = Choice.objects.filter(id=selected_id, question=question).first()
                if selected_choice and selected_choice.is_correct:
                    score += 1

            StudentAnswer.objects.create(
                attempt=attempt,
                question=question,
                selected_choice=selected_choice,
            )

        attempt.score = score
        attempt.save()
        return redirect('mocktest:result', attempt_id=attempt.id)

    return render(request, 'mocktest/take_test.html', {
        'test': test,
        'questions': questions,
    })


@login_required
def result_view(request, attempt_id):
    attempt = get_object_or_404(TestAttempt, id=attempt_id, student=request.user)
    answers = attempt.answers.select_related('question', 'selected_choice').all()
    return render(request, 'mocktest/result.html', {
        'attempt': attempt,
        'answers': answers,
    })


@login_required
def my_attempts_view(request):
    attempts = request.user.attempts.select_related('test').order_by('-started_at')
    return render(request, 'mocktest/my_attempts.html', {'attempts': attempts})
