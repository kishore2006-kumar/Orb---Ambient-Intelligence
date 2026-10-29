"""Error models and exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hub.drivers.registry import DriverUnavailableError


def error_response(code: str, message: str, status: int) -> JSONResponse:
    """Create a standard error JSON response."""
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": code, "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    from hub.api.deps import HubAuthError

    @app.exception_handler(HubAuthError)
    async def hub_auth_handler(request: Request, exc: HubAuthError) -> JSONResponse:
        return error_response("unauthorized", str(exc), 401)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        code = str(exc)
        messages: dict[str, str] = {
            "unknown_action": "Unknown action",
            "unsupported_capability": "Device does not support this action",
            "invalid_params": "Invalid parameters for this action",
            "invalid_capabilities": "Capabilities must be a non-empty subset of known actions",
            "invalid_name": "Name must be 1–80 characters",
            "unsupported_os_for_agent_pairing": "Only Windows laptop/PC can use the agent",
        }
        return error_response(code, messages.get(code, code), 422)

    @app.exception_handler(LookupError)
    async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
        code = str(exc)
        if code == "device_not_found":
            return error_response(code, "Device not found", 404)
        if code in ("invalid_code", "code_expired"):
            return error_response(code, "Pairing code invalid or expired", 400)
        return error_response(code, code, 404)

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
        code = str(exc)
        if code == "too_many_attempts":
            return error_response(code, "Too many failed attempts", 429)
        if code == "confirmation_required":
            return error_response(code, "Bulk medium-risk command requires confirm=true", 409)
        return error_response(code, code, 403)

    @app.exception_handler(TimeoutError)
    async def timeout_error_handler(request: Request, exc: TimeoutError) -> JSONResponse:
        code = str(exc)
        return error_response(code, "Pairing code has expired", 400)

    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError) -> JSONResponse:
        code = str(exc)
        return error_response(code, "ADB connection failed", 502)

    @app.exception_handler(DriverUnavailableError)
    async def driver_unavailable_handler(
        request: Request, exc: DriverUnavailableError
    ) -> JSONResponse:
        return error_response("driver_unavailable", str(exc), 503)

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        code = str(exc).strip("'\"")
        if code == "invalid_code":
            return error_response(code, "Invalid or used pairing code", 400)
        return error_response(code, code, 400)
