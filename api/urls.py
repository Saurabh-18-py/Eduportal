from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = 'api'

urlpatterns = [
    # --- auth ---
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    # --- notes ---
    path('subjects/', views.SubjectListView.as_view(), name='subject-list'),
    path('subjects/<int:subject_id>/chapters/', views.ChapterListView.as_view(), name='chapter-list'),
    path('chapters/<int:chapter_id>/notes/', views.ChapterNotesView.as_view(), name='chapter-notes'),
    path('pyq/', views.PYQListView.as_view(), name='pyq-list'),

    # --- mock tests ---
    path('subjects/<int:subject_id>/tests/', views.TestListView.as_view(), name='test-list'),
    path('tests/<int:test_id>/slice/<int:slice_number>/', views.TestSliceView.as_view(), name='test-slice'),
    path('tests/<int:test_id>/slice/<int:slice_number>/submit/', views.TestSliceSubmitView.as_view(), name='test-slice-submit'),
]
