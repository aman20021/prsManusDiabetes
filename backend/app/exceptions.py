from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.validation import ValidationException


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: list | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


async def validation_exception_handler(_: Request, exc: ValidationException) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )
