from typing import Any

from pydantic import BaseModel

from .errors import ErrorCode


class ToolError(BaseModel):
    code: str
    message: str
    fix_hint: str | None = None


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    warnings: list[str] = []
    error: ToolError | None = None


def ok(data: Any = None, *, warnings: list[str] | None = None) -> ToolResult:
    return ToolResult(ok=True, data=data, warnings=warnings or [])


def fail(code: ErrorCode, message: str, *, fix_hint: str | None = None) -> ToolResult:
    return ToolResult(
        ok=False,
        error=ToolError(code=code.value, message=message, fix_hint=fix_hint),
    )
