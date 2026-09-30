"""Application exceptions and the handlers that render them as :class:`ErrorResponse`.

Raise :class:`AppError` subclasses from services and endpoints. Framework errors
(unknown routes, validation failures) and unexpected exceptions are converted to the
same envelope, so clients only ever have to parse one error shape.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, ClassVar, cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.schemas.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that are part of the API contract."""

    status_code: ClassVar[int] = HTTPStatus.BAD_REQUEST
    code: ClassVar[str] = "bad_request"
    default_message: ClassVar[str] = "The request could not be processed."

    def __init__(
        self, message: str | None = None, *, details: list[dict[str, Any]] | None = None
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    default_message = "The requested resource was not found."


class AuthenticationRequiredError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "authentication_required"
    default_message = "Authentication is required to access this resource."


class PermissionDeniedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "permission_denied"
    default_message = "You do not have permission to perform this action."


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"
    default_message = "The request conflicts with the current state of the resource."


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id, details=details)
    )
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=response_headers,
    )


def _status_code_to_error_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast("AppError", exc)
    return _error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    error = cast("StarletteHTTPException", exc)
    return _error_response(
        request,
        status_code=error.status_code,
        code=_status_code_to_error_code(error.status_code),
        message=error.detail if isinstance(error.detail, str) else "The request failed.",
        headers=error.headers,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast("RequestValidationError", exc)
    # Drop the raw input: it can echo back secrets or personal data the client sent.
    details = [
        {key: value for key, value in item.items() if key not in {"input", "url", "ctx"}}
        for item in error.errors()
    ]
    return _error_response(
        request,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="The request is invalid.",
        details=jsonable_encoder(details),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        extra={"request_id": get_request_id(request), "path": request.url.path},
    )
    return _error_response(
        request,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    # Registered on Exception, Starlette runs this from its outermost middleware, so the
    # client always receives the standard envelope and never a stack trace.
    app.add_exception_handler(Exception, _handle_unexpected_error)
