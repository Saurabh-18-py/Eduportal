from django.urls import path
from . import views

app_name = 'doubtsolver'

urlpatterns = [
    path('', views.doubt_chat, name='chat'),
    path('ask/', views.ask_doubt, name='ask'),
]
