from django.urls import path
from . import views

app_name = 'mocktest'

urlpatterns = [
    path('subject/<int:subject_id>/tests/', views.test_list_view, name='test_list'),
    path('take/<int:test_id>/', views.take_test_view, name='take_test'),
    path('result/<int:attempt_id>/', views.result_view, name='result'),
    path('my-attempts/', views.my_attempts_view, name='my_attempts'),
]
