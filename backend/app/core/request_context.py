"""Request-id propagation and access logging.

Implemented as a pure ASGI middleware (not ``BaseHTTPMiddleware``) so it adds no
per-request task overhead and context variables set here are visible to endpoints.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

REQUEST_ID_HEADER: Final = "X-Request-ID"
# Accept caller-supplied ids (e.g. from a load balancer) only if they are short and safe
# to log; anything else is replaced so clients cannot inject content into our logs.
_VALID_REQUEST_ID: Final = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

access_logger = logging.getLogger("app.access")


def get_request_id(request: Request) -> str | None:
    """Return the id assigned to this request by :class:`RequestContextMiddleware`."""
    return getattr(request.state, "request_id", None) or request_id_var.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Request(scope).headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        # Stored on the scope as well as the context var: Starlette's outermost error
        # handler runs outside this middleware and reads it from ``request.state``.
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            access_logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_var.reset(token)
