from .contracts import ErrorCode, ErrorResponse


class DomainError(Exception):
    def __init__(self, code: ErrorCode, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.detail = ErrorResponse(code=code, message=message)
        self.status = status
