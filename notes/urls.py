from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('class/<int:class_level>/', views.class_subjects_view, name='class_subjects'),
    path('subject/<int:subject_id>/', views.subject_chapters_view, name='subject_chapters'),
    path('chapter/<int:chapter_id>/', views.chapter_notes_view, name='chapter_notes'),
]
