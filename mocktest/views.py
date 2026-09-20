from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.db.models import Avg, F, FloatField
from django.db.models.functions import Cast

from notes.models import Subject
from .models import Test, TestAttempt, StudentAnswer, Choice


def test_list_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    tests = subject.tests.all()

    # Group by chapter: each chapter's Test 1..N shown together under its own heading.
    chapter_groups = []
    for test in tests:
        if test.num_slices == 0:
            continue
        chapter_groups.append({
            'test': test,
            'chapter_title': test.title.replace(' - Practice Test', '').strip(),
            'slice_numbers': range(1, test.num_slices + 1),
        })

    return render(request, 'mocktest/test_list.html', {
        'subject': subject,
        'chapter_groups': chapter_groups,
    })


@login_required
def take_test_view(request, test_id, slice_number):
    test = get_object_or_404(Test, id=test_id)
    if slice_number < 1 or slice_number > test.num_slices:
        raise Http404("That test slot doesn't exist.")
    questions = test.get_slice_questions(slice_number)

    if request.method == 'POST':
        attempt = TestAttempt.objects.create(
            student=request.user,
            test=test,
            submitted_at=timezone.now(),
            total=len(questions),
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
        'slice_number': slice_number,
    })


@login_required
def result_view(request, attempt_id):
    attempt = get_object_or_404(TestAttempt, id=attempt_id, student=request.user)
    answers = attempt.answers.select_related('question', 'selected_choice').all()
    return render(request, 'mocktest/result.html', {
        'attempt': attempt,
        'answers': answers,
    })


def _calculate_streak(activity_dates):
    """activity_dates: a set of date objects the student did something on.
    Counts backwards from today (or yesterday, if nothing today yet)."""
    if not activity_dates:
        return 0
    today = timezone.localdate()
    cursor = today if today in activity_dates else today - timedelta(days=1)
    streak = 0
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@login_required
def my_attempts_view(request):
    attempts = request.user.attempts.select_related('test', 'test__subject').order_by('-started_at')
    graded = attempts.filter(total__gt=0)

    overall_avg = None
    if graded.exists():
        overall_avg = round(
            graded.annotate(pct=Cast(F('score'), FloatField()) * 100.0 / F('total')).aggregate(a=Avg('pct'))['a']
        )

    subject_stats = list(
        graded.values('test__subject__name')
        .annotate(pct=Avg(Cast(F('score'), FloatField()) * 100.0 / F('total')))
        .order_by('-pct')
    )
    for s in subject_stats:
        s['pct'] = round(s['pct'])

    chapters_practiced = attempts.values('test_id').distinct().count()

    # Streak: any day with a test attempt or a doubt asked counts as "studied".
    from doubtsolver.models import DoubtMessage
    activity_dates = set(attempts.dates('started_at', 'day'))
    activity_dates |= set(
        DoubtMessage.objects.filter(student=request.user, role='user').dates('created_at', 'day')
    )
    streak = _calculate_streak(activity_dates)

    return render(request, 'mocktest/my_attempts.html', {
        'attempts': attempts,
        'overall_avg': overall_avg,
        'tests_taken': attempts.count(),
        'chapters_practiced': chapters_practiced,
        'subject_stats': subject_stats,
        'streak': streak,
    })
