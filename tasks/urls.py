from django.urls import path

from . import views


app_name = "tasks"

urlpatterns = [
    path("", views.task_list, name="list"),
    path("create/", views.task_create, name="create"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("comments/attachments/<int:pk>/download/", views.comment_attachment_download, name="comment_attachment_download"),
    path("attachments/<int:pk>/download/", views.task_attachment_download, name="attachment_download"),
    path("submissions/<int:pk>/download/", views.submission_download, name="submission_download"),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/edit/", views.task_update, name="edit"),
    path("<int:pk>/delete/", views.task_delete, name="delete"),
    path("<int:pk>/start/", views.task_start, name="start"),
    path("<int:pk>/submit/", views.task_submit, name="submit"),
    path("<int:pk>/accept/", views.task_accept, name="accept"),
    path("<int:pk>/return/", views.task_return_for_revision, name="return_for_revision"),
]
