from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('push/register/', v.RegisterPushTokenView.as_view()),
    path('push/unregister/', v.UnregisterPushTokenView.as_view()),
    path('admin/notify/', v.NotifyView.as_view()),
    path('admin/upload/note/', v.UploadNoteView.as_view()),
    path('admin/upload/pyq/', v.UploadPYQView.as_view()),
]

from . import admin_manage as m  # noqa: E402

urlpatterns += [
    path('admin/overview/', m.OverviewView.as_view()),
    path('admin/users/', m.UserListView.as_view()),
    path('admin/users/<int:user_id>/', m.UserDetailView.as_view()),
]

from . import admin_content as c  # noqa: E402

urlpatterns += [
    path('admin/subjects/', c.SubjectCreateView.as_view()),
    path('admin/subjects/<int:subject_id>/', c.SubjectDetailView.as_view()),
    path('admin/chapters/', c.ChapterCreateView.as_view()),
    path('admin/chapters/<int:chapter_id>/', c.ChapterDetailView.as_view()),
    path('admin/notes/<int:note_id>/', c.NoteDetailView.as_view()),
    path('admin/pyq/<int:pyq_id>/', c.PYQDetailView.as_view()),
]

from . import attempt_views as av  # noqa: E402

urlpatterns += [
    path('attempts/<int:attempt_id>/', av.AttemptDetailView.as_view()),
]
