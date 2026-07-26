"""Application errors and safe FastAPI exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from vip_api.core.context import get_correlation_id
from vip_api.schemas.error import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """A deliberate, safe API failure with a stable machine code."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_response(
    *, status_code: int, code: str, message: str, details: list[ErrorDetail] | None = None
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            correlation_id=get_correlation_id(),
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


async def application_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApplicationError):
        raise TypeError("application_error_handler received an unexpected exception type")
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError("validation_error_handler received an unexpected exception type")
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            message=str(error["msg"]),
        )
        for error in exc.errors()
    ]
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="The request could not be validated.",
        details=details,
    )


async def http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise TypeError("http_error_handler received an unexpected exception type")
    code_messages = {
        status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "The requested resource was not found."),
        status.HTTP_405_METHOD_NOT_ALLOWED: ("METHOD_NOT_ALLOWED", "The method is not allowed."),
        status.HTTP_503_SERVICE_UNAVAILABLE: ("SERVICE_UNAVAILABLE", "The service is unavailable."),
    }
    code, message = code_messages.get(
        exc.status_code, ("HTTP_ERROR", "The request could not be completed.")
    )
    return error_response(status_code=exc.status_code, code=code, message=message)


async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Database operation failed", exc_info=exc)
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DATABASE_UNAVAILABLE",
        message="The database service is unavailable.",
    )


async def redis_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Redis operation failed", exc_info=exc)
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="REDIS_UNAVAILABLE",
        message="The Redis service is unavailable.",
    )


async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application exception", exc_info=exc)
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(RedisError, redis_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
