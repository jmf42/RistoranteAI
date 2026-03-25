from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.responses import JSONResponse, Response


def configure_logging(log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_request_id(request: Request) -> str:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    return request_id


def client_ip_for_request(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def json_log(logger_name: str, payload: dict) -> None:
    logger = logging.getLogger(logger_name)
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                **payload,
            },
            ensure_ascii=True,
            default=str,
        )
    )


async def logging_middleware(request: Request, call_next) -> Response:
    request_id = get_request_id(request)
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        duration_ms = round((perf_counter() - start) * 1000, 2)
        json_log(
            "app.request",
            {
                "event": "request_error",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "client_ip": client_ip_for_request(request),
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        error_response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
        error_response.headers["X-Request-ID"] = request_id
        return error_response
    duration_ms = round((perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    json_log(
        "app.request",
        {
            "event": "request_complete",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "status_code": response.status_code,
            "client_ip": client_ip_for_request(request),
            "duration_ms": duration_ms,
        },
    )
    return response
