class AppError(Exception):
    def __init__(self, statusCode, message, code="error", details=None):
        super().__init__(message)
        self.statusCode = int(statusCode)
        self.message = str(message)
        self.code = str(code)
        self.details = details

    def toDict(self):
        payload = {
            "success": False,
            "error": self.message,
            "detail": self.message,
            "code": self.code,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class BadRequestError(AppError):
    def __init__(self, message, code="bad_request", details=None):
        super().__init__(400, message, code=code, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message="Authentication required", code="unauthorized"):
        super().__init__(401, message, code=code)


class ForbiddenError(AppError):
    def __init__(self, message="Forbidden", code="forbidden"):
        super().__init__(403, message, code=code)


class NotFoundError(AppError):
    def __init__(self, message="Resource not found", code="not_found"):
        super().__init__(404, message, code=code)


class ConflictError(AppError):
    def __init__(self, message="Resource conflict", code="conflict"):
        super().__init__(409, message, code=code)


class UnprocessableError(AppError):
    def __init__(self, message="Validation failed", code="validation_error", details=None):
        super().__init__(422, message, code=code, details=details)


class RateLimitError(AppError):
    def __init__(self, message="Too many requests", code="rate_limited"):
        super().__init__(429, message, code=code)

