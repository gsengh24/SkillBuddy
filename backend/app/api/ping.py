"""``/ping``: a keep-alive for an external uptime monitor.

An outside monitor calls it every few minutes so Render Free doesn't put the API to sleep.
It must stay this cheap: no database (a query would wake Neon and spend its compute hours),
no AI provider, no email, no other service, no auth, session or cookies, and no rate limit
(nothing here could block a monitor). Its access-log line is written at debug level only
(``app/core/request_context.py``). It sits outside ``/api/v1`` on purpose: it is not part
of the versioned API.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])

PING_PATH = "/ping"


class PingResponse(BaseModel):
    status: Literal["ok"] = "ok"


# A fixed operation id: with two methods, FastAPI's generated one picks either at random,
# which made the committed OpenAPI spec flap between runs.
@router.api_route(
    PING_PATH,
    methods=["GET", "HEAD"],
    operation_id="ping",
    summary="Keep-alive for uptime monitors",
)
async def ping() -> PingResponse:
    """Always 200 `{"status": "ok"}` (HEAD: 200, no body). Touches nothing else."""
    return PingResponse()
