"""The admin Data and compliance page (A9), against real PostgreSQL, on a fresh database so
the counts and lists are exact."""

from __future__ import annotations

import csv
import gzip
import io
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime

import pytest
from alembic import command
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.models import AdminRole
from app.services.admin import data
from tests.conftest import SettingsFactory
from tests.integration.conftest import (
    CapturingDelivery,
    alembic_config,
    auth_client,
    run_sql,
    temporary_database,
)
from tests.integration.test_admin_portal import Person, admin_with, email, join, two_step
from tests.integration.test_auth_codes import error_code

DATA = "/api/v1/admin/data"
REASON = "Asked by email; identity checked."
OWNER = email("owner")


@pytest.fixture
def fresh_url() -> Iterator[str]:
    with temporary_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def settings(make_settings: SettingsFactory, fresh_url: str) -> Settings:
    return make_settings(
        database_url=fresh_url,
        admin_owner_emails=[OWNER],
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
        otp_request_limit_per_ip=1000,
        otp_verify_limit_per_ip=1000,
    )


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def owner_of(client: AsyncClient, settings: Settings, delivery: CapturingDelivery) -> Person:
    owner = await join(client, settings, delivery, OWNER)
    await two_step(client, owner)
    return owner


def user(url: str, address: str, terms_version: str | None = None) -> str:
    return str(
        run_sql(
            url,
            "INSERT INTO users (email, terms_version) VALUES (:e, :t) RETURNING id",
            e=address,
            t=terms_version,
        )[0]["id"]
    )


async def test_data_requests_are_listed_and_processed(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    asker = user(fresh_url, "asker@example.com")
    waiting = str(
        run_sql(fresh_url, "INSERT INTO data_exports (user_id) VALUES (:u) RETURNING id", u=asker)[
            0
        ]["id"]
    )
    done = str(
        run_sql(
            fresh_url,
            "INSERT INTO data_exports (user_id, status) VALUES (:u, 'expired') RETURNING id",
            u=asker,
        )[0]["id"]
    )
    leaving = user(fresh_url, "leaving@example.com")
    run_sql(
        fresh_url,
        "UPDATE users SET status = 'pending_deletion', deleted_at = now(), "
        "deletion_scheduled_for = now() + interval '30 days' WHERE id = :u",
        u=leaving,
    )
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        page = (await client.get(DATA, headers=owner.headers)).json()

        async def post(path: str) -> int:
            response = await client.post(path, json={"reason": REASON}, headers=owner.headers)
            return response.status_code

        processed = await post(f"{DATA}/exports/{waiting}/process")
        not_waiting = await post(f"{DATA}/exports/{done}/process")
        active = await post(f"{DATA}/deletions/{asker}/process")
        deleted = await post(f"{DATA}/deletions/{leaving}/process")
        missing = await post(f"{DATA}/deletions/{uuid.uuid4()}/process")

    exports = {item["id"]: item for item in page["exports_requested"]}
    assert exports[waiting]["processable"] is True
    assert exports[done]["processable"] is False
    requested = datetime.fromisoformat(exports[waiting]["requested_at"])
    assert (datetime.fromisoformat(exports[waiting]["deadline"]) - requested).days == 30
    assert [d["email"] for d in page["deletions_requested"]] == ["leaving@example.com"]
    assert (processed, not_waiting, active, deleted, missing) == (202, 409, 409, 204, 404)
    jobs = run_sql(fresh_url, "SELECT payload FROM jobs WHERE kind = 'build_data_export'")
    assert [job["payload"] for job in jobs] == [{"export_id": waiting}]
    assert run_sql(fresh_url, "SELECT 1 FROM users WHERE id = :u", u=leaving) == []
    assert (
        run_sql(fresh_url, "SELECT 1 FROM auth_events WHERE event_type = 'account_deleted'") != []
    )
    audit = run_sql(
        fresh_url,
        "SELECT action FROM admin_audit_log WHERE action LIKE 'data.%' ORDER BY created_at",
    )
    assert [row["action"] for row in audit] == ["data.export_processed", "data.deletion_processed"]


async def test_retention_and_consent(
    settings: Settings, delivery: CapturingDelivery, fresh_url: str
) -> None:
    user(fresh_url, "current@example.com", terms_version=settings.terms_version)
    user(fresh_url, "older@example.com", terms_version="2020-01-01")
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        page = (await client.get(DATA, headers=owner.headers)).json()

    rules = {item["data"]: item["rule"] for item in page["retention"]}
    assert rules["Admin audit log"] == "Kept without a time limit (append-only)"
    assert rules["AI call log"] == "30 days"
    assert rules["Email send log"] == "30 days"
    assert rules["Deleted accounts"] == (
        f"Permanently deleted {settings.account_deletion_grace_days} days after the request"
    )
    # The owner signed up just now, on the current terms.
    assert page["consent"] == {
        "terms_version": settings.terms_version,
        "total": 3,
        "current": 2,
        "older": 1,
    }


async def test_csv_exports_build_in_the_background_and_expire(
    settings: Settings,
    delivery: CapturingDelivery,
    fresh_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        helper = await join(client, settings, delivery, email("helper"))
        # A reason a spreadsheet would run as a formula.
        granted = await client.post(
            ADMIN_TEAM,
            json={
                "email": helper.email,
                "role": "moderator",
                "reason": "=HYPERLINK(evil) helps with reports",
            },
            headers=owner.headers,
        )
        assert granted.status_code == 201, granted.text
        started = await client.post(f"{DATA}/csv/users", headers=owner.headers)
        again = await client.post(f"{DATA}/csv/users", headers=owner.headers)
        audit = await client.post(f"{DATA}/csv/audit", headers=owner.headers)
        export_id = uuid.UUID(started.json()["id"])
        async with session_factory() as db:
            await data.build_export(db, export_id)
            await data.build_export(db, uuid.UUID(audit.json()["id"]))
        downloaded = await client.get(f"{DATA}/csv/{export_id}/download", headers=owner.headers)
        audit_file = await client.get(
            f"{DATA}/csv/{audit.json()['id']}/download", headers=owner.headers
        )
        run_sql(
            fresh_url,
            "UPDATE admin_exports SET expires_at = now() - interval '1 minute' WHERE id = :e",
            e=export_id,
        )
        expired = await client.get(f"{DATA}/csv/{export_id}/download", headers=owner.headers)

    assert started.status_code == 202, started.text
    assert started.json()["status"] == "queued"
    assert error_code(again) == "export_already_running"
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/gzip"
    rows = list(csv.reader(io.StringIO(gzip.decompress(downloaded.content).decode())))
    assert rows[0] == data.USERS_HEADER
    assert OWNER in {row[1] for row in rows[1:]}
    audit_rows = list(csv.reader(io.StringIO(gzip.decompress(audit_file.content).decode())))
    assert "'=HYPERLINK(evil) helps with reports" in {row[6] for row in audit_rows[1:]}
    assert error_code(expired) == "admin_export_not_found"


ADMIN_TEAM = "/api/v1/admin/team"


async def test_only_owners_and_admins_and_the_audit_csv_for_owners(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery)
        people = {
            role: await admin_with(client, settings, delivery, owner, role)
            for role in (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)
        }
        views = {
            role.value: (await client.get(DATA, headers=person.headers)).status_code
            for role, person in people.items()
        }
        admin_audit = await client.post(
            f"{DATA}/csv/audit", headers=people[AdminRole.ADMIN].headers
        )
        admin_users = await client.post(
            f"{DATA}/csv/users", headers=people[AdminRole.ADMIN].headers
        )

    assert views == {"admin": 200, "moderator": 403, "readonly": 403}
    assert admin_audit.status_code == 403
    assert admin_users.status_code == 202
