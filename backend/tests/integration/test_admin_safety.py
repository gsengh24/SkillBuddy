"""Reports and safety (A3), against real PostgreSQL: attached messages, decisions, appeals,
block counts, and the rule that attached messages are the only message text admins see."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.main import create_app
from app.models import AdminRole
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_admin_portal import Person as Admin
from tests.integration.test_admin_portal import admin_with, email, join, two_step
from tests.integration.test_auth_codes import error_code, request_code, verify
from tests.integration.test_chat import connect, say

SAFETY = "/api/v1/admin/safety"
REASON = "Sent the same spam link to several people."


@pytest.fixture
def owner_email() -> str:
    return email("owner")


@pytest.fixture
def settings(
    make_settings: SettingsFactory, migrated_database_url: str, owner_email: str
) -> Settings:
    return make_settings(
        database_url=migrated_database_url,
        admin_owner_emails=[owner_email],
        admin_requests_per_minute=600,
        admin_two_step_attempts=20,
        ai_llm_enabled=False,
        otp_request_limit_per_email=10,
        reports_per_day=50,
    )


async def owner_of(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, address: str
) -> Admin:
    owner = await join(client, settings, delivery, address)
    await two_step(client, owner)
    return owner


async def chat(
    client: AsyncClient, settings: Settings, delivery: CapturingDelivery, url: str
) -> Any:
    """Asha and Ravi, connected, with six messages; Ravi reports Asha."""
    asha, ravi, connection = await connect(client, settings, delivery, url)
    ids = []
    for number in range(6):
        speaker = asha if number % 2 == 0 else ravi
        ids.append((await say(client, speaker, connection, f"line {number}")).json()["id"])
    return asha, ravi, connection, ids


def audit(settings: Settings, target: str, action: str) -> int:
    return int(
        run_sql(
            settings.database_url.unicode_string(),
            "SELECT count(*) AS n FROM admin_audit_log WHERE target_id = :t AND action = :a",
            t=target,
            a=action,
        )[0]["n"]
    )


async def test_reporters_attach_up_to_five_messages_and_only_those_are_shown(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        asha, ravi, connection, ids = await chat(client, settings, delivery, migrated_database_url)
        too_many = await client.post(
            f"/api/v1/people/{asha.id}/report",
            json={"reason": "spam", "message_ids": ids},
            headers=ravi.headers,
        )
        other_chat = await client.post(
            f"/api/v1/people/{asha.id}/report",
            json={"reason": "spam", "message_ids": [str(uuid.uuid4())]},
            headers=ravi.headers,
        )
        filed = await client.post(
            f"/api/v1/people/{asha.id}/report",
            json={"reason": "spam", "message_ids": [ids[4], ids[0]]},
            headers=ravi.headers,
        )
        case = (
            await client.get(f"{SAFETY}/reports/{filed.json()['id']}", headers=owner.headers)
        ).json()
        # A message report copies the reported message only.
        message_report = await client.post(
            f"/api/v1/messages/{ids[2]}/report", json={"reason": "harassment"}, headers=ravi.headers
        )
        message_case = (
            await client.get(
                f"{SAFETY}/reports/{message_report.json()['id']}", headers=owner.headers
            )
        ).json()
        queue = (await client.get(f"{SAFETY}/reports", headers=owner.headers)).json()

    assert too_many.status_code == 422
    assert error_code(other_chat) == "attached_message_not_found"
    assert filed.status_code == 201
    chat_lines = [item["body"] for item in case["attached"] if item["label"] is None]
    assert chat_lines == ["line 0", "line 4"]
    assert case["report"]["reported"]["id"] == asha.id
    assert case["report"]["reporter"]["id"] == ravi.id
    assert set(case["reported_history"]) == {
        "reports_against",
        "reports_filed",
        "times_blocked",
        "upheld_reports",
    }
    assert [item["body"] for item in message_case["attached"]] == ["line 2"]
    # The queue carries no message text at all.
    mine = next(item for item in queue["items"] if item["id"] == filed.json()["id"])
    assert "line" not in str(mine)
    assert connection


async def test_decisions_act_notify_and_write_one_audit_entry_each(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, owner_email: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        results: dict[str, Any] = {}
        for decision in ("dismiss", "warn", "suspend", "ban"):
            asha, ravi, _, ids = await chat(client, settings, delivery, url)
            report = (
                await client.post(
                    f"/api/v1/messages/{ids[0]}/report",
                    json={"reason": "spam"},
                    headers=ravi.headers,
                )
            ).json()
            if decision == "warn":
                started = await client.post(
                    f"{SAFETY}/reports/{report['id']}/start-review",
                    json={"reason": "Looking at this one now."},
                    headers=owner.headers,
                )
                assert started.json()["status"] == "in_review"
            decided = await client.post(
                f"{SAFETY}/reports/{report['id']}/decide",
                json={"decision": decision, "reason": REASON},
                headers=owner.headers,
            )
            again = await client.post(
                f"{SAFETY}/reports/{report['id']}/decide",
                json={"decision": decision, "reason": REASON},
                headers=owner.headers,
            )
            notices = (await client.get("/api/v1/notifications", headers=ravi.headers)).json()
            results[decision] = (report["id"], asha.id, decided, again, notices)

    for decision, (report_id, asha_id, decided, again, notices) in results.items():
        assert decided.status_code == 200, decided.text
        assert decided.json()["decision"] == decision
        assert error_code(again) == "report_already_resolved"
        assert "report_reviewed" in [item["kind"] for item in notices["items"]]
        assert audit(settings, report_id, f"report.decided.{decision}") == 1
        status = run_sql(url, "SELECT status FROM users WHERE id = :u", u=asha_id)[0]["status"]
        assert (
            status
            == {"dismiss": "active", "warn": "active", "suspend": "suspended", "ban": "banned"}[
                decision
            ]
        )
        emails = run_sql(
            url,
            "SELECT count(*) AS n FROM jobs WHERE kind = 'send_safety_notice' "
            "AND payload->>'user_id' = :u",
            u=asha_id,
        )[0]["n"]
        assert emails == (0 if decision == "dismiss" else 1)
    assert audit(settings, results["warn"][0], "report.review_started") == 1


async def test_a_suspended_person_appeals_once_and_an_admin_overturns_it(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, owner_email: str
) -> None:
    url = migrated_database_url
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        asha, ravi, _, ids = await chat(client, settings, delivery, url)
        report = (
            await client.post(
                f"/api/v1/messages/{ids[0]}/report", json={"reason": "spam"}, headers=ravi.headers
            )
        ).json()
        await client.post(
            f"{SAFETY}/reports/{report['id']}/decide",
            json={"decision": "suspend", "reason": REASON},
            headers=owner.headers,
        )
        address = run_sql(url, "SELECT email FROM users WHERE id = :u", u=asha.id)[0]["email"]
        await request_code(client, address)
        refused = await verify(client, address, delivery.last_code(address), consent=False)
        token = refused.json()["error"]["details"][0]["appeal_token"]
        bad = await client.post(
            "/api/v1/appeals", json={"token": token[:-2] + "xx", "appeal": "Please"}
        )
        sent = await client.post(
            "/api/v1/appeals", json={"token": token, "appeal": "It was a mistake."}
        )
        twice = await client.post("/api/v1/appeals", json={"token": token, "appeal": "Again"})
        listed = (await client.get(f"{SAFETY}/appeals", headers=owner.headers)).json()
        mine = next(item for item in listed["items"] if item["person"]["id"] == asha.id)
        overturned = await client.post(
            f"{SAFETY}/appeals/{mine['id']}/decide",
            json={"outcome": "overturn", "reason": "The link was a school project."},
            headers=owner.headers,
        )
        decided_twice = await client.post(
            f"{SAFETY}/appeals/{mine['id']}/decide",
            json={"outcome": "uphold", "reason": "The link was a school project."},
            headers=owner.headers,
        )
        not_needed = await client.post("/api/v1/appeals", json={"token": token, "appeal": "Hi"})

    assert error_code(refused) == "account_suspended"
    assert error_code(bad) == "invalid_appeal_link"
    assert sent.status_code == 201
    assert error_code(twice) == "appeal_exists"
    assert mine["appeal"] == "It was a mistake."
    assert mine["against"] == "suspended"
    assert overturned.json()["status"] == "overturned"
    assert error_code(decided_twice) == "appeal_already_decided"
    assert (
        run_sql(url, "SELECT status FROM users WHERE id = :u", u=asha.id)[0]["status"] == "active"
    )
    assert error_code(not_needed) == "nothing_to_appeal"
    assert audit(settings, mine["id"], "appeal.overturned") == 1


async def test_block_counts_and_roles(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str, owner_email: str
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await owner_of(client, settings, delivery, owner_email)
        readonly = await admin_with(client, settings, delivery, owner, AdminRole.READONLY)
        moderator = await admin_with(client, settings, delivery, owner, AdminRole.MODERATOR)
        asha, ravi, _, ids = await chat(client, settings, delivery, migrated_database_url)
        await client.post("/api/v1/blocks", json={"user_id": asha.id}, headers=ravi.headers)
        stats = (await client.get(f"{SAFETY}/blocks", headers=readonly.headers)).json()
        report = (
            await client.post(
                f"/api/v1/messages/{ids[0]}/report", json={"reason": "spam"}, headers=ravi.headers
            )
        ).json()
        read_queue = await client.get(f"{SAFETY}/reports", headers=readonly.headers)
        read_case = await client.get(f"{SAFETY}/reports/{report['id']}", headers=readonly.headers)
        read_decide = await client.post(
            f"{SAFETY}/reports/{report['id']}/decide",
            json={"decision": "warn", "reason": REASON},
            headers=readonly.headers,
        )
        mod_decide = await client.post(
            f"{SAFETY}/reports/{report['id']}/decide",
            json={"decision": "warn", "reason": REASON},
            headers=moderator.headers,
        )

    assert stats["total"] >= 1
    assert stats["last_30_days"] >= 1
    assert any(item["user_id"] == asha.id for item in stats["most_blocked"])
    assert set(stats["most_blocked"][0]) == {"user_id", "email", "status", "times"}
    assert read_queue.status_code == 200
    assert error_code(read_case) == "admin_permission_denied"
    assert error_code(read_decide) == "admin_permission_denied"
    assert mod_decide.status_code == 200


# --- no message text but what reporters attach -------------------------------------------

# Field names that could carry chat text, and the only places they may appear in the admin
# API: attached messages (and the older report routes' identical copy), an admin's own
# note, and the report's own description of what was reported.
TEXT_FIELDS = {"body", "text", "content", "message", "message_text"}
ALLOWED = {
    ("AttachedMessage", "body"),
    ("ReportedMessage", "body"),
    # An admin's own private note, written and read in the portal.
    ("NoteIn", "body"),
    ("NoteOut", "body"),
    # The API's own error message (the standard error envelope).
    ("ErrorDetail", "message"),
}


def _refs(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            found.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            found |= _refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= _refs(value)
    return found


def test_attached_messages_are_the_only_message_text_in_the_admin_api(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    components = schema["components"]["schemas"]
    reachable: set[str] = set()
    pending = set().union(
        *(_refs(item) for path, item in schema["paths"].items() if path.startswith("/api/v1/admin"))
    )
    while pending:
        name = pending.pop()
        if name in reachable or name not in components:
            continue
        reachable.add(name)
        pending |= _refs(components[name])
    offenders = {
        (name, field)
        for name in reachable
        for field in components[name].get("properties", {})
        if field in TEXT_FIELDS and (name, field) not in ALLOWED
    }
    assert "AttachedMessage" in reachable
    assert offenders == set()
