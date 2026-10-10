"""Download my data (Prompt 12C): request, build in a job, download by emailed link, purge.

The API only records the request and queues ``build_data_export``. The job gathers the
person's own data into JSON, gzips it into the row, and emails a link with a token that is
stored only as a hash. Downloading needs both the person's session and that token. The
file is dropped when the link expires; the row goes after ``data_export_retention_days``.
"""

from __future__ import annotations

import gzip
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any, Final

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import constant_time_equals, generate_token, hash_token, mask_email
from app.jobs.queue import enqueue
from app.models import (
    AdminExport,
    AdminExportStatus,
    Connection,
    DataExport,
    DataExportStatus,
    EmailPurpose,
    Intro,
    MatchRequest,
    Message,
    Profile,
    Team,
    TeamMember,
    TeamMessage,
    User,
)
from app.schemas.profile import ProfileOut
from app.services.email.budget import may_send, record_sent
from app.services.email.send_log import logged_sender
from app.services.email.templates import data_export_email

logger = logging.getLogger(__name__)

FORMAT_VERSION: Final = 1
# A file is never allowed to grow without bound: messages are kept 90 days and capped in
# length, so this is far above any real account.
MAX_MESSAGES: Final = 20_000
# Admin CSV exports (A9): rows are deleted this many days after they were asked for.
ADMIN_EXPORT_RETENTION_DAYS: Final = 30


class DataExportRecentError(ConflictError):
    code = "data_export_recent"
    default_message = "You asked for your data recently. Check your email, or try again later."


class DataExportNotFoundError(NotFoundError):
    code = "data_export_not_found"
    default_message = "That download doesn't exist."


class DataExportUnavailableError(AppError):
    status_code = HTTPStatus.GONE
    code = "data_export_unavailable"
    default_message = "This download link has expired or isn't valid. Ask for a new one."


async def request_export(db: AsyncSession, settings: Settings, user: User) -> DataExport:
    """Record a request and queue the build. One at a time, and one per cooldown period."""
    since = datetime.now(UTC) - timedelta(hours=settings.data_export_cooldown_hours)
    recent = await db.scalar(
        select(DataExport.id).where(
            DataExport.user_id == user.id,
            DataExport.status != DataExportStatus.FAILED,
            or_(
                DataExport.created_at > since,
                DataExport.status == DataExportStatus.REQUESTED,
            ),
        )
    )
    if recent is not None:
        raise DataExportRecentError
    export = DataExport(user_id=user.id, status=DataExportStatus.REQUESTED)
    db.add(export)
    await db.flush()
    # Imported here: app.jobs.tasks imports this module for the job's handler.
    from app.jobs.tasks import BUILD_DATA_EXPORT

    await enqueue(db, BUILD_DATA_EXPORT, {"export_id": str(export.id)})
    await db.commit()
    await db.refresh(export)
    logger.info("data_export_requested", extra={"export_id": str(export.id)})
    return export


async def recent_exports(db: AsyncSession, user: User, limit: int = 5) -> list[DataExport]:
    rows = await db.scalars(
        select(DataExport)
        .where(DataExport.user_id == user.id)
        .order_by(DataExport.created_at.desc())
        .limit(limit)
    )
    return list(rows)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def collect(db: AsyncSession, settings: Settings, user: User) -> dict[str, Any]:
    """Everything the person has given us or written, and their side of each connection.
    Other people appear only as ids, plus the name they shared once you connected."""
    profile = await db.get(Profile, user.id)
    requests = await db.scalars(
        select(MatchRequest)
        .where(MatchRequest.user_id == user.id)
        .order_by(MatchRequest.created_at)
    )
    intros = await db.scalars(
        select(Intro)
        .where(or_(Intro.sender_id == user.id, Intro.recipient_id == user.id))
        .order_by(Intro.created_at)
    )
    connections = list(
        await db.scalars(
            select(Connection)
            .where(or_(Connection.user_a == user.id, Connection.user_b == user.id))
            .order_by(Connection.created_at)
        )
    )
    others = {c.id: c.user_b if c.user_a == user.id else c.user_a for c in connections}
    names: dict[uuid.UUID, str] = {}
    if others:
        rows = await db.execute(
            select(Profile.user_id, Profile.display_name).where(
                Profile.user_id.in_(set(others.values()))
            )
        )
        names = dict(rows.tuples().all())
    messages: list[dict[str, Any]] = []
    if connections:
        side = {c.id: c.user_a == user.id for c in connections}
        rows_m = await db.scalars(
            select(Message)
            .where(Message.connection_id.in_(list(side)))
            .order_by(Message.created_at)
            .limit(MAX_MESSAGES)
        )
        messages = [
            {
                "connection_id": str(m.connection_id),
                "from": "you" if m.from_a == side[m.connection_id] else "them",
                "text": m.body,
                "sent_at": _iso(m.created_at),
            }
            for m in rows_m
        ]
    # Teams (ADR 0016): the teams the person is in, and only their own team messages.
    team_rows = await db.execute(
        select(Team, TeamMember.created_at)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id, Team.closed_at.is_(None))
        .order_by(TeamMember.created_at)
    )
    teams = [
        {
            "id": str(team.id),
            "name": team.name,
            "purpose": team.purpose,
            "you_are_the_owner": team.owner_id == user.id,
            "joined_at": _iso(joined_at),
        }
        for team, joined_at in team_rows.tuples()
    ]
    own_team_messages = await db.scalars(
        select(TeamMessage)
        .where(TeamMessage.sender_id == user.id)
        .order_by(TeamMessage.created_at)
        .limit(MAX_MESSAGES)
    )
    team_messages = [
        {"team_id": str(m.team_id), "text": m.body, "sent_at": _iso(m.created_at)}
        for m in own_team_messages
    ]
    return {
        "format_version": FORMAT_VERSION,
        "service": settings.app_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "account": {
            "email": user.email,
            "status": user.status,
            "created_at": _iso(user.created_at),
            "last_login_at": _iso(user.last_login_at),
            "age_confirmed_at": _iso(user.age_confirmed_at),
            "terms_version": user.terms_version,
            "terms_accepted_at": _iso(user.terms_accepted_at),
        },
        "profile": (
            ProfileOut.from_profile(
                profile, consent_version=settings.ai_consent_version
            ).model_dump(mode="json")
            if profile
            else None
        ),
        "requests": [
            {
                "id": str(r.id),
                "text": r.raw_text,
                "requested_intent": r.requested_intent,
                "intent": r.intent,
                "status": r.status,
                "created_at": _iso(r.created_at),
            }
            for r in requests
        ],
        "intros": [
            {
                "id": str(i.id),
                "direction": "sent" if i.sender_id == user.id else "received",
                "other_user_id": str(i.recipient_id if i.sender_id == user.id else i.sender_id),
                "status": i.status,
                "note": i.note,
                "created_at": _iso(i.created_at),
                "responded_at": _iso(i.responded_at),
            }
            for i in intros
        ],
        "connections": [
            {
                "id": str(c.id),
                "other_user_id": str(others[c.id]),
                "other_display_name": names.get(others[c.id]) or None,
                "created_at": _iso(c.created_at),
                "ended_at": _iso(c.ended_at),
            }
            for c in connections
        ],
        "messages": messages,
        "teams": teams,
        "team_messages": team_messages,
    }


async def build_export(db: AsyncSession, settings: Settings, export_id: uuid.UUID) -> None:
    """The job: build the file and email the link. Runs again safely (only a request that
    is still ``requested`` is built)."""
    export = await db.get(DataExport, export_id, with_for_update=True)
    if export is None or export.status != DataExportStatus.REQUESTED:
        return
    user = await db.get(User, export.user_id)
    if user is None:
        return
    if not settings.web_app_url or not await may_send(db, settings, EmailPurpose.DATA_EXPORT):
        # No way to send the link today: say so, and let the person ask again.
        export.status = DataExportStatus.FAILED
        await db.commit()
        logger.warning("data_export_failed", extra={"reason": "email_unavailable"})
        return
    payload = gzip.compress(
        json.dumps(await collect(db, settings, user), ensure_ascii=False, indent=2).encode()
    )
    token = generate_token()
    now = datetime.now(UTC)
    url = f"{settings.web_app_url.rstrip('/')}/you/download?export={export.id}&token={token}"
    # Email first, then mark it ready: if sending fails the job is retried with a new token.
    sender = logged_sender(
        settings,
        db,
        template="data_export",
        retry_kind="build_data_export",
        retry_payload={"export_id": str(export.id)},
    )
    message_id = await sender.send(
        data_export_email(settings, user.email, url, settings.data_export_link_hours)
    )
    export.status = DataExportStatus.READY
    export.token_hash = hash_token(token)
    export.payload = payload
    export.size_bytes = len(payload)
    export.ready_at = now
    export.expires_at = now + timedelta(hours=settings.data_export_link_hours)
    await record_sent(  # commits the export too
        db,
        settings,
        purpose=EmailPurpose.DATA_EXPORT,
        recipient=user.email,
        provider=sender.provider,
        message_id=message_id,
    )
    logger.info(
        "data_export_ready",
        extra={"export_id": str(export.id), "bytes": len(payload), "email": mask_email(user.email)},
    )


async def download(db: AsyncSession, user: User, export_id: uuid.UUID, token: str) -> bytes:
    """The JSON file, for its owner with the emailed token, until the link expires."""
    export = await db.get(DataExport, export_id)
    if export is None or export.user_id != user.id:
        raise DataExportNotFoundError
    now = datetime.now(UTC)
    if (
        export.status != DataExportStatus.READY
        or export.payload is None
        or export.token_hash is None
        or (export.expires_at is not None and export.expires_at <= now)
        or not constant_time_equals(export.token_hash, hash_token(token))
    ):
        raise DataExportUnavailableError
    export.downloaded_at = now
    data = gzip.decompress(export.payload)
    await db.commit()
    return data


async def purge(db: AsyncSession, settings: Settings) -> dict[str, int]:
    """Daily: drop expired files, give up on requests stuck for a day, delete old rows."""
    now = datetime.now(UTC)
    expired = await db.execute(
        update(DataExport)
        .where(DataExport.status == DataExportStatus.READY, DataExport.expires_at <= now)
        .values(status=DataExportStatus.EXPIRED, payload=None, token_hash=None)
    )
    stuck = await db.execute(
        update(DataExport)
        .where(
            DataExport.status == DataExportStatus.REQUESTED,
            DataExport.created_at <= now - timedelta(days=1),
        )
        .values(status=DataExportStatus.FAILED)
    )
    deleted = await db.execute(
        delete(DataExport).where(
            DataExport.created_at <= now - timedelta(days=settings.data_export_retention_days)
        )
    )
    # Admin CSV exports (A9): the file goes when its link expires, the row after 30 days.
    await db.execute(
        update(AdminExport)
        .where(AdminExport.status == AdminExportStatus.READY, AdminExport.expires_at <= now)
        .values(status=AdminExportStatus.EXPIRED, payload=None)
    )
    await db.execute(
        update(AdminExport)
        .where(
            AdminExport.status.in_((AdminExportStatus.QUEUED, AdminExportStatus.RUNNING)),
            AdminExport.created_at <= now - timedelta(days=1),
        )
        .values(status=AdminExportStatus.FAILED)
    )
    await db.execute(
        delete(AdminExport).where(
            AdminExport.created_at <= now - timedelta(days=ADMIN_EXPORT_RETENTION_DAYS)
        )
    )
    await db.commit()
    counts = {
        "expired": int(getattr(expired, "rowcount", 0) or 0),
        "failed": int(getattr(stuck, "rowcount", 0) or 0),
        "deleted": int(getattr(deleted, "rowcount", 0) or 0),
    }
    logger.info("data_exports_purged", extra=counts)
    return counts
