from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from teams.models import Team, TeamMember

from .forms import (
    ChatMessageEditForm,
    ChatMessageForm,
    PrivateMessageEditForm,
    PrivateMessageForm,
    TeamMeetingForm,
)
from .models import ChatMessage, PrivateChat, PrivateMessage


User = get_user_model()


WRITER_ROLES = (
    TeamMember.Role.OWNER,
    TeamMember.Role.DEVELOPER,
    TeamMember.Role.TESTER,
)


def get_user_chat_teams(user):
    return (
        Team.objects.filter(Q(owner=user) | Q(members__user=user))
        .annotate(last_message_at=Max("chat_messages__created_at"))
        .distinct()
        .order_by("name")
    )


def get_team_role(user, team):
    if team.owner_id == user.id:
        return TeamMember.Role.OWNER

    membership = team.members.filter(user=user).first()
    if membership:
        return membership.role

    return None


def can_write_to_chat(role):
    return role in WRITER_ROLES


def can_edit_message(user, chat_message, role):
    return (
        not chat_message.is_deleted
        and chat_message.author_id == user.id
        and can_write_to_chat(role)
    )


def can_delete_message(user, chat_message, role):
    if chat_message.is_deleted:
        return False
    if role == TeamMember.Role.OWNER:
        return True
    return chat_message.author_id == user.id and can_write_to_chat(role)


def can_edit_meeting_link(role):
    return role == TeamMember.Role.OWNER


def get_private_chat_team_ids(user):
    return (
        Team.objects.filter(
            Q(owner=user) | Q(members__user=user, members__role__in=WRITER_ROLES)
        )
        .distinct()
        .values_list("id", flat=True)
    )


def get_available_private_users(user):
    team_ids = get_private_chat_team_ids(user)
    return (
        User.objects.filter(
            Q(owned_teams__id__in=team_ids)
            | Q(team_memberships__team_id__in=team_ids, team_memberships__role__in=WRITER_ROLES)
        )
        .exclude(pk=user.pk)
        .distinct()
        .order_by("username")
    )


def get_existing_private_chat_user_ids(user):
    chat_pairs = PrivateChat.objects.filter(
        Q(participant_1=user) | Q(participant_2=user)
    ).values_list("participant_1_id", "participant_2_id")

    user_ids = set()
    for participant_1_id, participant_2_id in chat_pairs:
        user_ids.add(participant_2_id if participant_1_id == user.id else participant_1_id)

    return user_ids


def can_start_private_chat(user, other_user):
    return get_available_private_users(user).filter(pk=other_user.pk).exists()


def get_existing_private_chat(user, other_user):
    return PrivateChat.objects.filter(
        Q(participant_1=user, participant_2=other_user)
        | Q(participant_1=other_user, participant_2=user)
    ).first()


def get_user_private_chats(user):
    return (
        PrivateChat.objects.filter(Q(participant_1=user) | Q(participant_2=user))
        .select_related("participant_1", "participant_2")
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-updated_at")
    )


def can_access_private_chat(user, chat):
    if user.id not in (chat.participant_1_id, chat.participant_2_id):
        return False

    return can_start_private_chat(user, chat.get_other_participant(user))


def get_accessible_private_chat(user, pk):
    chat = get_object_or_404(get_user_private_chats(user), pk=pk)
    if not can_access_private_chat(user, chat):
        raise PermissionDenied
    return chat


def get_accessible_private_message(user, pk):
    private_message = get_object_or_404(
        PrivateMessage.objects.select_related("chat", "chat__participant_1", "chat__participant_2", "author"),
        pk=pk,
        chat__in=get_user_private_chats(user),
    )
    if not can_access_private_chat(user, private_message.chat):
        raise PermissionDenied
    return private_message


def can_edit_private_message(user, private_message):
    return private_message.author_id == user.id and not private_message.is_deleted


def can_delete_private_message(user, private_message):
    return private_message.author_id == user.id and not private_message.is_deleted


def get_accessible_message(user, pk):
    return get_object_or_404(
        ChatMessage.objects.select_related("team", "team__owner", "author", "deleted_by").filter(
            Q(team__owner=user) | Q(team__members__user=user)
        ).distinct(),
        pk=pk,
    )


def get_attachment_response(chat_message, request):
    if chat_message.is_deleted or not chat_message.attachment:
        raise Http404

    use_thumbnail = request.GET.get("thumbnail") == "1" and chat_message.is_image_attachment
    file_field = chat_message.attachment

    if use_thumbnail:
        if not chat_message.thumbnail:
            chat_message.create_thumbnail()
            chat_message.refresh_from_db(fields=["thumbnail"])
        if chat_message.thumbnail:
            file_field = chat_message.thumbnail

    filename = Path(file_field.name).name
    force_download = request.GET.get("download") == "1"
    return FileResponse(
        file_field.open("rb"),
        as_attachment=force_download or not chat_message.is_image_attachment,
        filename=filename,
    )


@login_required
def chat_list(request):
    teams = get_user_chat_teams(request.user)
    return render(request, "chats/list.html", {"teams": teams})


@login_required
def private_chat_list(request):
    private_chats = list(get_user_private_chats(request.user))
    for private_chat in private_chats:
        private_chat.other_user = private_chat.get_other_participant(request.user)

    existing_chat_user_ids = get_existing_private_chat_user_ids(request.user)
    available_users = get_available_private_users(request.user).exclude(pk__in=existing_chat_user_ids)
    has_private_chat_options = bool(private_chats) or available_users.exists()
    return render(
        request,
        "chats/private_list.html",
        {
            "private_chats": private_chats,
            "available_users": available_users,
            "has_private_chat_options": has_private_chat_options,
        },
    )


@login_required
def private_chat_start(request, user_id):
    other_user = get_object_or_404(get_available_private_users(request.user), pk=user_id)
    existing_chat = get_existing_private_chat(request.user, other_user)
    if existing_chat:
        return redirect("chats:private_detail", chat_id=existing_chat.pk)

    participant_1_id, participant_2_id = sorted([request.user.id, other_user.id])
    private_chat, _ = PrivateChat.objects.get_or_create(
        participant_1_id=participant_1_id,
        participant_2_id=participant_2_id,
    )
    return redirect("chats:private_detail", chat_id=private_chat.pk)


@login_required
def private_chat_detail(request, chat_id):
    private_chat = get_accessible_private_chat(request.user, chat_id)
    other_user = private_chat.get_other_participant(request.user)

    if request.method == "POST":
        form = PrivateMessageForm(request.POST, request.FILES)
        if form.is_valid():
            private_message = form.save(commit=False)
            private_message.chat = private_chat
            private_message.author = request.user
            private_message.save()
            private_chat.save(update_fields=["updated_at"])
            return redirect("chats:private_detail", chat_id=private_chat.pk)
    else:
        form = PrivateMessageForm()

    private_messages = private_chat.messages.select_related("author").order_by("created_at")
    for private_message in private_messages:
        private_message.can_edit = can_edit_private_message(request.user, private_message)
        private_message.can_delete = can_delete_private_message(request.user, private_message)

    return render(
        request,
        "chats/private_detail.html",
        {
            "private_chat": private_chat,
            "other_user": other_user,
            "private_messages": private_messages,
            "form": form,
        },
    )


@login_required
def team_chat(request, team_id):
    team = get_object_or_404(get_user_chat_teams(request.user), pk=team_id)
    role = get_team_role(request.user, team)
    can_send = can_write_to_chat(role)

    if request.method == "POST":
        if not can_send:
            raise PermissionDenied

        form = ChatMessageForm(request.POST, request.FILES)
        if form.is_valid():
            chat_message = form.save(commit=False)
            chat_message.team = team
            chat_message.author = request.user
            chat_message.save()
            return redirect("chats:team_chat", team_id=team.pk)
    else:
        form = ChatMessageForm()

    chat_messages = team.chat_messages.select_related("author", "deleted_by").order_by("created_at")
    for chat_message in chat_messages:
        chat_message.can_edit = can_edit_message(request.user, chat_message, role)
        chat_message.can_delete = can_delete_message(request.user, chat_message, role)

    return render(
        request,
        "chats/team_chat.html",
        {
            "team": team,
            "chat_messages": chat_messages,
            "form": form,
            "can_send": can_send,
            "can_edit_meeting": can_edit_meeting_link(role),
        },
    )


@login_required
def message_edit(request, pk):
    chat_message = get_accessible_message(request.user, pk)
    role = get_team_role(request.user, chat_message.team)
    if not can_edit_message(request.user, chat_message, role):
        raise PermissionDenied

    if request.method == "POST":
        form = ChatMessageEditForm(request.POST, instance=chat_message)
        if form.is_valid():
            edited_message = form.save(commit=False)
            edited_message.edited_at = timezone.now()
            edited_message.save(update_fields=["text", "edited_at"])
            return redirect("chats:team_chat", team_id=chat_message.team_id)
    else:
        form = ChatMessageEditForm(instance=chat_message)

    return render(request, "chats/message_form.html", {"form": form, "chat_message": chat_message})


@login_required
@require_POST
def message_delete(request, pk):
    chat_message = get_accessible_message(request.user, pk)
    role = get_team_role(request.user, chat_message.team)
    if not can_delete_message(request.user, chat_message, role):
        raise PermissionDenied

    chat_message.is_deleted = True
    chat_message.deleted_at = timezone.now()
    chat_message.deleted_by = request.user
    chat_message.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
    return redirect("chats:team_chat", team_id=chat_message.team_id)


@login_required
def private_message_edit(request, pk):
    private_message = get_accessible_private_message(request.user, pk)
    if not can_edit_private_message(request.user, private_message):
        raise PermissionDenied

    if request.method == "POST":
        form = PrivateMessageEditForm(request.POST, instance=private_message)
        if form.is_valid():
            edited_message = form.save(commit=False)
            edited_message.edited_at = timezone.now()
            edited_message.save(update_fields=["content", "edited_at"])
            return redirect("chats:private_detail", chat_id=private_message.chat_id)
    else:
        form = PrivateMessageEditForm(instance=private_message)

    return render(
        request,
        "chats/private_message_form.html",
        {"form": form, "private_message": private_message},
    )


@login_required
@require_POST
def private_message_delete(request, pk):
    private_message = get_accessible_private_message(request.user, pk)
    if not can_delete_private_message(request.user, private_message):
        raise PermissionDenied

    private_message.is_deleted = True
    private_message.deleted_at = timezone.now()
    private_message.save(update_fields=["is_deleted", "deleted_at"])
    return redirect("chats:private_detail", chat_id=private_message.chat_id)


@login_required
def private_message_download(request, pk):
    private_message = get_accessible_private_message(request.user, pk)
    return get_attachment_response(private_message, request)


@login_required
def message_download(request, pk):
    chat_message = get_accessible_message(request.user, pk)
    return get_attachment_response(chat_message, request)


@login_required
def meeting_link_edit(request, team_id):
    team = get_object_or_404(get_user_chat_teams(request.user), pk=team_id)
    role = get_team_role(request.user, team)
    if not can_edit_meeting_link(role):
        raise PermissionDenied

    if request.method == "POST":
        form = TeamMeetingForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, "Посилання на онлайн-зустріч оновлено.")
            return redirect("chats:team_chat", team_id=team.pk)
    else:
        form = TeamMeetingForm(instance=team)

    return render(request, "chats/meeting_form.html", {"team": team, "form": form})
