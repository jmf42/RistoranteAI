#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None
    detail: str


class SmokeClient:
    def __init__(self, frontend_url: str, backend_url: str) -> None:
        self.frontend_url = frontend_url.rstrip("/")
        self.backend_url = backend_url.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        self.origin = self.frontend_url

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        origin: str | None = None,
    ) -> tuple[int, dict[str, str], str]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = origin
        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                response_headers = {key.lower(): value for key, value in response.headers.items()}
                return response.status, response_headers, body
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, {key.lower(): value for key, value in exc.headers.items()}, body
        except URLError as exc:
            raise RuntimeError(f"{url} failed: {exc.reason}") from exc


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_json(body: str) -> Any:
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def main() -> int:
    try:
        frontend_url = require_env("FRONTEND_URL")
        backend_url = require_env("BACKEND_URL")
        owner_email = require_env("OWNER_EMAIL")
        owner_password = require_env("OWNER_PASSWORD")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    client = SmokeClient(frontend_url, backend_url)
    results: list[CheckResult] = []

    def record(name: str, ok: bool, status: int | None, detail: str) -> None:
        results.append(CheckResult(name=name, ok=ok, status=status, detail=detail))

    try:
        status, _, _ = client.request(f"{frontend_url}/")
        record("frontend root", status == 200, status, "expected 200 from dashboard root")

        status, _, _ = client.request(f"{frontend_url}/login")
        record("frontend login", status == 200, status, "expected 200 from login page")

        status, _, body = client.request(f"{backend_url}/health")
        payload = parse_json(body)
        record(
            "backend health",
            status == 200 and payload == {"status": "ok"},
            status,
            body,
        )

        status, _, body = client.request(f"{backend_url}/healthz")
        payload = parse_json(body)
        healthz_ok = status == 200 and payload == {"status": "ok"}
        healthz_detail = body
        if (
            not healthz_ok
            and backend_url.endswith(".run.app")
            and status == 404
            and "<!DOCTYPE html>" in body
        ):
            healthz_ok = True
            healthz_detail = "Cloud Run default domains intercept /healthz; /health and /readyz remain verified."
        record(
            "backend healthz",
            healthz_ok,
            status,
            healthz_detail,
        )

        status, _, body = client.request(f"{backend_url}/readyz")
        payload = parse_json(body)
        record(
            "backend readyz",
            status == 200 and payload == {"status": "ok"},
            status,
            body,
        )

        status, headers, body = client.request(
            f"{backend_url}/api/auth/login",
            method="POST",
            payload={"email": owner_email, "password": owner_password},
            origin=client.origin,
        )
        cors_origin = headers.get("access-control-allow-origin")
        cookie_header = headers.get("set-cookie", "")
        cookie_header_lower = cookie_header.lower()
        login_ok = (
            status == 200
            and cors_origin == client.origin
            and "secure" in cookie_header_lower
            and "samesite=none" in cookie_header_lower
        )
        record("backend login", login_ok, status, f"cors={cors_origin!r}")

        status, _, body = client.request(f"{backend_url}/api/auth/me", origin=client.origin)
        me_payload = parse_json(body)
        me_ok = status == 200 and me_payload.get("user", {}).get("email") == owner_email
        record("session me", me_ok, status, body)

        status, _, body = client.request(
            f"{backend_url}/api/restaurants/current",
            origin=client.origin,
        )
        restaurant_payload = parse_json(body)
        restaurant_id = restaurant_payload.get("id")
        record("restaurant current", status == 200 and bool(restaurant_id), status, body)

        query = urlencode({"restaurant_id": restaurant_id}) if restaurant_id else ""
        analytics_url = f"{backend_url}/api/analytics/overview?{query}" if query else ""
        bookings_url = f"{backend_url}/api/bookings?{query}" if query else ""
        calls_url = f"{backend_url}/api/calls?{query}" if query else ""

        for name, url in (
            ("analytics overview", analytics_url),
            ("bookings list", bookings_url),
            ("calls list", calls_url),
        ):
            if not url:
                record(name, False, None, "missing restaurant id")
                continue
            status, _, body = client.request(url, origin=client.origin)
            record(name, status == 200, status, body[:180])

        export_targets = (
            ("bookings export", f"{backend_url}/api/bookings/export?{query}"),
            ("calls export", f"{backend_url}/api/calls/export?{query}"),
        )
        for name, url in export_targets:
            if not query:
                record(name, False, None, "missing restaurant id")
                continue
            status, headers, body = client.request(url, origin=client.origin)
            content_type = headers.get("content-type", "")
            record(name, status == 200 and "text/csv" in content_type, status, content_type or body[:180])

        if bookings_url:
            status, _, body = client.request(bookings_url, origin=client.origin)
            bookings_payload = parse_json(body) or []
            if status == 200 and bookings_payload:
                first_booking_id = bookings_payload[0].get("id")
                events_url = (
                    f"{backend_url}/api/bookings/{first_booking_id}/events?{query}" if first_booking_id else ""
                )
                if events_url:
                    status, _, body = client.request(events_url, origin=client.origin)
                    events_payload = parse_json(body) or []
                    record(
                        "booking events",
                        status == 200 and isinstance(events_payload, list),
                        status,
                        body[:180],
                    )
    except RuntimeError as exc:
        record("request failure", False, None, str(exc))

    failures = [result for result in results if not result.ok]
    for result in results:
        badge = "OK" if result.ok else "FAIL"
        status_text = f" [{result.status}]" if result.status is not None else ""
        print(f"{badge}{status_text} {result.name}: {result.detail}")

    if failures:
        print(f"\nSmoke test failed: {len(failures)} check(s) failed.", file=sys.stderr)
        return 1

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
