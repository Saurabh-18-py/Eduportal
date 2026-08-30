from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('class/<int:class_level>/', views.class_subjects_view, name='class_subjects'),
    path('subject/<int:subject_id>/', views.subject_chapters_view, name='subject_chapters'),
    path('chapter/<int:chapter_id>/', views.chapter_notes_view, name='chapter_notes'),
    path('pyq/class/<int:class_level>/', views.pyq_years_view, name='pyq_years'),
    path('pyq/class/<int:class_level>/year/<int:year>/', views.pyq_subjects_view, name='pyq_subjects'),
    path('note/<int:note_id>/view/', views.view_note_pdf, name='view_note_pdf'),
    path('pyq-paper/<int:paper_id>/view/', views.view_pyq_pdf, name='view_pyq_pdf'),
]
