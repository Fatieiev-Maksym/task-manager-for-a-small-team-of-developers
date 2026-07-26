from django.urls import path

from . import views


app_name = "chats"

urlpatterns = [
    path("", views.chat_list, name="list"),
    path("private/", views.private_chat_list, name="private_list"),
    path("private/start/<int:user_id>/", views.private_chat_start, name="private_start"),
    path("private/<int:chat_id>/", views.private_chat_detail, name="private_detail"),
    path("private/messages/<int:pk>/edit/", views.private_message_edit, name="private_message_edit"),
    path("private/messages/<int:pk>/delete/", views.private_message_delete, name="private_message_delete"),
    path("private/messages/<int:pk>/download/", views.private_message_download, name="private_message_download"),
    path("teams/<int:team_id>/", views.team_chat, name="team_chat"),
    path("teams/<int:team_id>/meeting/", views.meeting_link_edit, name="meeting_edit"),
    path("messages/<int:pk>/edit/", views.message_edit, name="message_edit"),
    path("messages/<int:pk>/delete/", views.message_delete, name="message_delete"),
    path("messages/<int:pk>/download/", views.message_download, name="message_download"),
]
