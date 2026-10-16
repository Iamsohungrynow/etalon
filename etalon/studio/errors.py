"""Errors the API answers with: ``{code, message}``, or a contract model of its own."""

from pydantic import BaseModel


class ApiError(BaseModel):
    """Body of every error response the API sends itself (validation errors excepted)."""

    code: str
    message: str


class StudioError(Exception):
    """Answer ``status`` with an ApiError body."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ModelError(Exception):
    """Answer ``status`` with a contract model as the body (ScriptError, AlreadyRunning)."""

    def __init__(self, status: int, body: BaseModel) -> None:
        super().__init__(f"{status}: {body!r}")
        self.status = status
        self.body = body
