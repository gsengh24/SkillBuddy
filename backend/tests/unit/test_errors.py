"""Every failure, expected or not, is rendered as the same ErrorResponse envelope."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI, Query
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.main import create_app

router = APIRouter(prefix="/_test")


@router.get("/not-found")
async def raise_not_found() -> None:
    raise NotFoundError("Profile not found.")


@router.get("/conflict")
async def raise_conflict() -> None:
    raise ConflictError(details=[{"field": "email"}])


@router.get("/validated")
async def validated(limit: Annotated[int, Query(ge=1, le=10)]) -> dict[str, int]:
    return {"limit": limit}


@router.get("/crash")
async def crash() -> None:
    raise RuntimeError("database password is hunter2")


@router.get("/protected", dependencies=[Depends(get_current_user)])
async def protected() -> None:
    return None


@pytest.fixture
async def error_client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app: FastAPI = create_app(settings)
    app.include_router(router)
    # Starlette re-raises unhandled errors after responding; keep the response instead.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _assert_envelope(body: dict[str, object], code: str) -> dict[str, object]:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "request_id", "details"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert error["message"]
    return error


async def test_app_error_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/not-found")

    assert response.status_code == 404
    error = _assert_envelope(response.json(), "not_found")
    assert error["message"] == "Profile not found."
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_app_error_carries_details(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/conflict")

    assert response.status_code == 409
    error = _assert_envelope(response.json(), "conflict")
    assert error["details"] == [{"field": "email"}]


async def test_unknown_route_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.get("/does-not-exist")

    assert response.status_code == 404
    _assert_envelope(response.json(), "not_found")


async def test_method_not_allowed_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.post("/api/v1/health")

    assert response.status_code == 405
    _assert_envelope(response.json(), "method_not_allowed")


async def test_validation_error_uses_envelope_without_echoing_input(
    error_client: AsyncClient,
) -> None:
    response = await error_client.get("/_test/validated", params={"limit": "999"})

    assert response.status_code == 422
    error = _assert_envelope(response.json(), "validation_error")
    details = error["details"]
    assert isinstance(details, list)
    assert details[0]["loc"] == ["query", "limit"]
    assert "input" not in details[0]


async def test_unhandled_error_hides_internals(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/crash")

    assert response.status_code == 500
    error = _assert_envelope(response.json(), "internal_error")
    assert "hunter2" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_protected_route_without_session_returns_401(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/protected")

    assert response.status_code == 401
    _assert_envelope(response.json(), "authentication_required")
