"""Domain errors with stable codes and HTTP status mappings."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status = 409

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


class NotFound(DomainError):
    status = 404


class Forbidden(DomainError):
    status = 403


class Unauthenticated(DomainError):
    status = 401


class StaleRevision(DomainError):
    status = 412


class Conflict(DomainError):
    status = 409


class Unsupported(DomainError):
    status = 422


class Throttled(DomainError):
    status = 429


class Unavailable(DomainError):
    status = 503
