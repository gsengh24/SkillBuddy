"""The admin Users page API (A2). Every route goes through ``require_admin``; each action
has its own route, so the route tests hold every action to the permission table.

No ``from __future__ import annotations`` here: the action routes are made in a loop, and
FastAPI must see each one's own permission check, which a string annotation would hide.
"""

import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_deps import AdminContext, DbDep, client_ip, require_admin
from app.api.deps import SettingsDep, require_json
from app.models import UserStatus
from app.schemas.admin_users import (
    ActionIn,
    NoteIn,
    NoteOut,
    ProfileSummary,
    TimelineItem,
    UserDetail,
    UserPage,
    UserRow,
)
from app.schemas.errors import ErrorResponse
from app.services.admin import users
from app.services.admin.permissions import Permission

_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED.value: {"model": ErrorResponse},
    HTTPStatus.FORBIDDEN.value: {"model": ErrorResponse},
}

router = APIRouter(prefix="/admin/users", tags=["admin"], responses=_ERRORS)

Viewer = Annotated[AdminContext, Depends(require_admin(Permission.VIEW_USERS))]
Moderator = Annotated[AdminContext, Depends(require_admin(Permission.SUSPEND_USERS))]


@router.get("", summary="Users, newest first")
async def list_users(
    _: Viewer,
    db: DbDep,
    q: Annotated[str | None, Query(max_length=100, description="Name or email.")] = None,
    status: UserStatus | None = None,
    intent: Annotated[str | None, Query(max_length=32)] = None,
    flagged: bool = False,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=users.PAGE_MAX)] = users.PAGE_DEFAULT,
) -> UserPage:
    filters = users.Filters(q=q, status=status, intent=intent, flagged=flagged)
    rows, next_cursor = await users.page(db, filters, cursor=cursor, limit=limit)
    return UserPage(
        items=[UserRow.from_row(row) for row in rows],
        next_cursor=next_cursor,
        total=await users.total(db, filters),
    )


@router.get(
    "/{user_id}",
    summary="One user",
    responses={HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}},
)
async def get_user(user_id: uuid.UUID, _: Viewer, db: DbDep) -> UserDetail:
    found = await users.detail(db, user_id)
    user, profile = found.user, found.profile
    return UserDetail(
        id=user.id,
        email=user.email,
        status=user.status,  # type: ignore[arg-type]  # the CHECK keeps it to these values
        suspended_until=user.suspended_until,
        deletion_scheduled_for=user.deletion_scheduled_for,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        email_verified_at=user.email_verified_at,
        sign_in_methods=found.sign_in_methods,
        profile=ProfileSummary(
            display_name=profile.display_name,
            headline=profile.headline,
            city=profile.city,
            about_text=profile.raw_about_text,
            intents=list(profile.intents),
            visibility=profile.visibility,
            parse_status=profile.parse_status,
        )
        if profile
        else None,
        counts=found.counts,
        timeline=[TimelineItem(at=at, event=event) for at, event in found.timeline],
        notes=[NoteOut.from_note(note) for note in found.notes],
    )


_ACTION_ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse, "description": "`user_not_found`."},
    HTTPStatus.CONFLICT.value: {
        "model": ErrorResponse,
        "description": "`cannot_act_on_admin`, `invalid_status_change` or `no_profile`.",
    },
}


def _action_route(
    action: users.UserAction, summary: str, description: str
) -> Callable[..., Awaitable[None]]:
    async def endpoint(
        user_id: uuid.UUID,
        body: ActionIn,
        request: Request,
        admin: Annotated[AdminContext, Depends(require_admin(users.ACTION_PERMISSION[action]))],
        db: DbDep,
        settings: SettingsDep,
    ) -> None:
        await users.act(db, settings, admin.who, user_id, action, body.reason, client_ip(request))

    endpoint.__doc__ = description
    router.add_api_route(
        f"/{{user_id}}/{action.value}",
        endpoint,
        methods=["POST"],
        status_code=HTTPStatus.NO_CONTENT,
        summary=summary,
        dependencies=[Depends(require_json)],
        responses=_ACTION_ERRORS,
        name=f"admin_user_{action.value.replace('-', '_')}",
    )
    return endpoint


_action_route(
    users.UserAction.SUSPEND,
    "Suspend for 7 days",
    "Signed out at once; can't sign in; out of matching and other people's lists. Lifts "
    "itself after 7 days.",
)
_action_route(users.UserAction.UNSUSPEND, "Lift a suspension", "The account is active again.")
_action_route(
    users.UserAction.BAN,
    "Ban",
    "Signed out at once; can't sign in until the ban is reversed.",
)
_action_route(users.UserAction.UNBAN, "Reverse a ban", "The account is active again.")
_action_route(
    users.UserAction.SIGN_OUT, "Sign out everywhere", "Ends every session of the account."
)
_action_route(
    users.UserAction.CLEAR_BIO,
    "Clear the about text",
    "Removes the description and what was read from it; they leave matching until they write "
    "a new one.",
)
_action_route(
    users.UserAction.SCHEDULE_DELETION,
    "Schedule deletion",
    "The same grace period as when people delete their own account "
    "(ACCOUNT_DELETION_GRACE_DAYS); signed out at once.",
)


@router.post(
    "/{user_id}/notes",
    status_code=HTTPStatus.CREATED,
    summary="Add a private note",
    dependencies=[Depends(require_json)],
    responses={HTTPStatus.NOT_FOUND.value: {"model": ErrorResponse}},
)
async def add_note(
    user_id: uuid.UUID,
    body: NoteIn,
    request: Request,
    admin: Moderator,
    db: DbDep,
    settings: SettingsDep,
) -> NoteOut:
    """Only admins see notes. The audit log records that one was added, not its text."""
    note = await users.add_note(db, settings, admin.who, user_id, body.body, client_ip(request))
    return NoteOut.from_note(note)
