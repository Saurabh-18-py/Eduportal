from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('push/register/', v.RegisterPushTokenView.as_view()),
    path('push/unregister/', v.UnregisterPushTokenView.as_view()),
    path('admin/notify/', v.NotifyView.as_view()),
    path('admin/upload/note/', v.UploadNoteView.as_view()),
    path('admin/upload/pyq/', v.UploadPYQView.as_view()),
]
