"""Detailed mock-test report: time analysis, comparison and rank."""


def analyze(rows, total_seconds=0, previous=None, others=None, my_score=0):
    total = len(rows)
    correct = [r for r in rows if r['status'] == 'correct']
    wrong = [r for r in rows if r['status'] == 'wrong']
    skipped = [r for r in rows if r['status'] == 'skipped']
    answered = correct + wrong
    sum_secs = sum(r['seconds'] for r in rows)
    time_used = total_seconds or sum_secs
    avg_answered = (sum(r['seconds'] for r in answered) / len(answered)) if answered else 0

    def pick(items, fn, need_time=True):
        pool = [r for r in items if r['seconds'] > 0] if need_time else list(items)
        if not pool:
            return None
        r = fn(pool, key=lambda x: (x['seconds'], x['index'] if fn is min else -x['index']))
        return {'index': r['index'], 'question_id': r['question_id'], 'seconds': r['seconds']}

    careless = [
        r['index'] for r in wrong
        if r['seconds'] <= max(4, 0.6 * avg_answered)
    ]
    sinks = sorted(
        [r for r in rows if r['seconds'] >= 20 and r['seconds'] >= 1.5 * avg_answered],
        key=lambda x: -x['seconds'],
    )[:3]

    pct = round(len(correct) * 100 / total) if total else 0
    accuracy = round(len(correct) * 100 / len(answered)) if answered else 0

    prev = None
    if previous and previous.get('total'):
        prev_pct = round(previous['score'] * 100 / previous['total'])
        prev = {
            'score': previous['score'],
            'total': previous['total'],
            'percentage': prev_pct,
            'delta': pct - prev_pct,
        }

    rank = None
    if others:
        rank = {
            'rank': 1 + sum(1 for o in others if o > my_score),
            'participants': len(others) + 1,
            'percentile': round(100 * sum(1 for o in others if o < my_score) / len(others)),
        }

    return {
        'summary': {
            'total': total,
            'correct': len(correct),
            'wrong': len(wrong),
            'skipped': len(skipped),
            'attempted': len(answered),
            'percentage': pct,
            'accuracy': accuracy,
            'time_used': int(time_used),
            'avg_seconds': round(sum_secs / total) if total else 0,
        },
        'fastest': pick(answered, min),
        'fastest_correct': pick(correct, min),
        'slowest': pick(rows, max),
        'careless': careless,
        'time_sinks': [r['index'] for r in sinks],
        'per_question': [
            {'index': r['index'], 'question_id': r['question_id'], 'status': r['status'], 'seconds': r['seconds']}
            for r in rows
        ],
        'previous': prev,
        'rank': rank,
    }


def build_report(attempt):
    from mocktest.models import TestAttempt

    answers = list(
        attempt.answers.select_related('selected_choice')
        .order_by('question__order', 'question__id')
    )
    rows = []
    for i, a in enumerate(answers, 1):
        if a.selected_choice_id is None:
            status = 'skipped'
        elif a.selected_choice and a.selected_choice.is_correct:
            status = 'correct'
        else:
            status = 'wrong'
        rows.append({
            'index': i,
            'question_id': a.question_id,
            'status': status,
            'seconds': a.time_taken_seconds or 0,
        })

    previous = None
    others = []
    if attempt.slice_number:
        base = TestAttempt.objects.filter(
            test=attempt.test, slice_number=attempt.slice_number, submitted_at__isnull=False
        )
        prev = (
            base.filter(student=attempt.student, id__lt=attempt.id)
            .order_by('-id').first()
        )
        if prev:
            previous = {'score': prev.score, 'total': prev.total}
        best = {}
        for sid, sc in base.exclude(student=attempt.student).values_list('student_id', 'score'):
            best[sid] = max(best.get(sid, 0), sc)
        others = list(best.values())

    return analyze(
        rows,
        total_seconds=attempt.duration_seconds or 0,
        previous=previous,
        others=others,
        my_score=attempt.score,
    )
