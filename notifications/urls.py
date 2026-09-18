from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),
    path('send/', views.send_page, name='send_page'),
]
