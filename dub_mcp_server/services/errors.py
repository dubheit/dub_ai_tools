# Copyright 2025 Dubhe Srls
# License LGPL-3

from typing import Optional


class McpError(Exception):
    code: str = "SERVER_ERROR"
    http_status: int = 200

    def __init__(
        self,
        message: str = "",
        details: Optional[dict] = None,
        http_status: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message or self.__class__.__name__
        self.details = details or {}
        if http_status:
            self.http_status = http_status

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class Unauthenticated(McpError):
    code = "UNAUTHENTICATED"


class AuthzDenied(McpError):
    code = "AUTHZ_DENIED"


class ModelUnknown(McpError):
    code = "MODEL_UNKNOWN"


class FieldUnknown(McpError):
    code = "FIELD_UNKNOWN"


class InvalidDomain(McpError):
    code = "INVALID_DOMAIN"


class InvalidValues(McpError):
    code = "INVALID_VALUES"


class RecordNotFound(McpError):
    code = "RECORD_NOT_FOUND"


class RateLimited(McpError):
    code = "RATE_LIMITED"


class Timeout(McpError):
    code = "TIMEOUT"


class PayloadTooLarge(McpError):
    code = "PAYLOAD_TOO_LARGE"
