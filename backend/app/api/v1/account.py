"""The signed-in user's own account."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Response

from app.api.deps import SettingsDep
from app.api.session_cookies import clear_session_cookies
from app.api.v1.auth import AuthDep, AuthServiceDep, ClientDep
from app.schemas.auth import DeletionScheduledOut

router = APIRouter(tags=["account"])


@router.delete("/me", status_code=HTTPStatus.ACCEPTED, summary="Delete my account")
async def delete_account(
    auth: AuthDep,
    response: Response,
    service: AuthServiceDep,
    client: ClientDep,
    settings: SettingsDep,
) -> DeletionScheduledOut:
    """Schedule permanent deletion after the grace period (30 days by default).

    Signs out every device immediately; signing in is refused during the grace period.
    """
    scheduled_for = await service.request_deletion(auth.user, client)
    clear_session_cookies(response, settings)
    return DeletionScheduledOut(deletion_scheduled_for=scheduled_for)
