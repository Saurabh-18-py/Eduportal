from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Avg, Count

from .forms import SignupForm, ProfileForm, AvatarForm
from .models import StudentProfile, Avatar


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
