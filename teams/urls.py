from django.urls import path

from . import views


app_name = "teams"

urlpatterns = [
    path("", views.team_list, name="list"),
    path("create/", views.team_create, name="create"),
    path("<int:pk>/", views.team_detail, name="detail"),
    path("<int:pk>/leave/", views.team_leave, name="leave"),
    path("<int:pk>/edit/", views.team_update, name="edit"),
    path("<int:pk>/delete/", views.team_delete, name="delete"),
    path("<int:pk>/members/add/", views.team_member_add, name="member_add"),
    path("<int:pk>/members/<int:member_pk>/edit/", views.team_member_edit, name="member_edit"),
    path("<int:pk>/members/<int:member_pk>/delete/", views.team_member_delete, name="member_delete"),
]
