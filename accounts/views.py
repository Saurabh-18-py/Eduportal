from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q

from .forms import SignupForm, ProfileForm, AvatarForm, MessageForm
from .models import StudentProfile, Avatar, Message


def get_admin_user():
    """The site owner every student's conversation goes to (first superuser found)."""
    return User.objects.filter(is_superuser=True).order_by('id').first()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password'],
            )
            StudentProfile.objects.create(
                user=user,
                class_level=form.cleaned_data['class_level'],
            )
            admin_user = get_admin_user()
            if admin_user and admin_user != user:
                Message.objects.create(
                    sender=admin_user,
                    recipient=user,
                    text=(
                        f"Welcome to EduPortal, {user.username}! 🎉 I'm Saurabh, "
                        f"the person behind this site. If you ever have a question, "
                        f"feedback, or run into an issue, just reply right here."
                    ),
                )
            login(request, user)
            messages.success(request, "Account created successfully!")
            return redirect('home')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url or 'home')
        # form.is_valid() is False for wrong username/password/inactive account.
        # AuthenticationForm already sets a helpful non_field_error, but we also
        # add a message so it shows in the site-wide alert banner.
        messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('home')


@login_required
def dashboard_view(request):
    profile = getattr(request.user, 'profile', None)
    return render(request, 'accounts/dashboard.html', {'profile': profile})


@login_required
def profile_view(request):
    from mocktest.models import TestAttempt

    profile = getattr(request.user, 'profile', None)
    if profile is None and not request.user.is_superuser and not request.user.is_staff:
        profile = StudentProfile.objects.create(user=request.user, class_level=10)

    if request.method == 'POST' and 'save_profile' in request.POST:
        form = ProfileForm(request.POST)
        if form.is_valid():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.email = form.cleaned_data['email']
            request.user.save()
            if profile:
                profile.class_level = form.cleaned_data['class_level']
                profile.phone = form.cleaned_data['phone']
                profile.save()
            messages.success(request, "Profile updated.")
            return redirect('accounts:profile')
    else:
        form = ProfileForm(initial={
            'first_name': request.user.first_name,
            'email': request.user.email,
            'class_level': profile.class_level if profile else None,
            'phone': profile.phone if profile else '',
        })

    if request.method == 'POST' and 'save_avatar' in request.POST:
        avatar_form = AvatarForm(request.POST)
        if avatar_form.is_valid() and profile:
            profile.avatar = avatar_form.cleaned_data['avatar']
            profile.save()
            messages.success(request, "Avatar updated.")
            return redirect('accounts:profile')
    else:
        avatar_form = AvatarForm(initial={'avatar': profile.avatar if profile else None})

    attempts = TestAttempt.objects.filter(
        student=request.user, submitted_at__isnull=False
    ).select_related('test__subject')

    total_attempts = attempts.count()
    avg_score_pct = 0
    if total_attempts:
        percentages = [
            (a.score / a.total * 100) if a.total else 0 for a in attempts
        ]
        avg_score_pct = round(sum(percentages) / len(percentages), 1)

    subject_stats = (
        attempts.values('test__subject__name')
        .annotate(attempts_count=Count('id'), avg_score=Avg('score'))
        .order_by('test__subject__name')
    )

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'form': form,
        'avatar_form': avatar_form,
        'avatars': Avatar.objects.filter(is_active=True),
        'total_attempts': total_attempts,
        'avg_score_pct': avg_score_pct,
        'subject_stats': subject_stats,
    })


@login_required
def send_message_view(request):
    """A student's chat thread with the site admin - view history and reply."""
    if request.user.is_superuser:
        return redirect('accounts:inbox')

    admin_user = get_admin_user()
    if not admin_user:
        messages.error(request, "Messaging isn't set up yet.")
        return redirect('home')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                sender=request.user,
                recipient=admin_user,
                text=form.cleaned_data['text'],
            )
            return redirect('accounts:send_message')
    else:
        form = MessageForm()

    thread = Message.objects.filter(
        Q(sender=request.user, recipient=admin_user) | Q(sender=admin_user, recipient=request.user)
    ).select_related('sender').order_by('created_at')

    thread.filter(sender=admin_user, recipient=request.user, is_read=False).update(is_read=True)

    return render(request, 'accounts/send_message.html', {
        'form': form,
        'thread': thread,
        'admin_user': admin_user,
    })


@login_required
def inbox_view(request):
    """List of every student conversation, most recently active first - superuser only."""
    if not request.user.is_superuser:
        raise PermissionDenied("You don't have access to the inbox.")

    partner_ids = set(
        Message.objects.filter(sender=request.user).values_list('recipient_id', flat=True)
    ) | set(
        Message.objects.filter(recipient=request.user).values_list('sender_id', flat=True)
    )
    partner_ids.discard(request.user.id)

    conversations = []
    for student in User.objects.filter(id__in=partner_ids):
        last_message = Message.objects.filter(
            Q(sender=student, recipient=request.user) | Q(sender=request.user, recipient=student)
        ).order_by('-created_at').first()
        unread_count = Message.objects.filter(
            sender=student, recipient=request.user, is_read=False
        ).count()
        conversations.append({
            'student': student,
            'last_message': last_message,
            'unread_count': unread_count,
        })

    conversations.sort(key=lambda c: c['last_message'].created_at if c['last_message'] else 0, reverse=True)

    return render(request, 'accounts/inbox.html', {'conversations': conversations})


@login_required
def conversation_view(request, student_id):
    """The admin's view of one student's thread - reply directly here."""
    if not request.user.is_superuser:
        raise PermissionDenied("You don't have access to this.")

    student = get_object_or_404(User, id=student_id)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                sender=request.user,
                recipient=student,
                text=form.cleaned_data['text'],
            )
            return redirect('accounts:conversation', student_id=student.id)
    else:
        form = MessageForm()

    thread = Message.objects.filter(
        Q(sender=student, recipient=request.user) | Q(sender=request.user, recipient=student)
    ).select_related('sender').order_by('created_at')

    thread.filter(sender=student, recipient=request.user, is_read=False).update(is_read=True)

    return render(request, 'accounts/conversation.html', {
        'form': form,
        'thread': thread,
        'student': student,
    })
