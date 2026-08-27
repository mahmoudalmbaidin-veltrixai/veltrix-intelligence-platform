"""Live API certification probe. Prints statuses only. Never prints passwords or tokens.

Required environment:
  VIP_PROBE_EMAIL
  VIP_PROBE_PASSWORD
  VIP_PROBE_ORG
  VIP_PROBE_WS

Optional:
  VIP_PROBE_BASE (default http://localhost:8000)
  VIP_PROBE_VIEWER_EMAIL / VIP_PROBE_VIEWER_PASSWORD
  VIP_PROBE_OTHER_ORG / VIP_PROBE_OTHER_WS
  VIP_PROBE_MUTATE=1  to create a throwaway invitation (default off)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("VIP_PROBE_BASE", "http://localhost:8000").rstrip("/")
ORG = os.environ.get("VIP_PROBE_ORG", "")
WS = os.environ.get("VIP_PROBE_WS", "")
OTHER_ORG = os.environ.get("VIP_PROBE_OTHER_ORG", "")
OTHER_WS = os.environ.get("VIP_PROBE_OTHER_WS", "")
MUTATE = os.environ.get("VIP_PROBE_MUTATE", "") == "1"


class Client:
    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def request(
        self, method: str, path: str, body: dict | None = None, tenant: bool = False
    ) -> tuple[int, object]:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if tenant:
            if not ORG or not WS:
                raise RuntimeError("VIP_PROBE_ORG and VIP_PROBE_WS are required for tenant calls")
            headers["X-Organization-ID"] = ORG
            headers["X-Workspace-ID"] = WS
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode()) if raw else None
                return resp.status, parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode()) if raw else None
            except json.JSONDecodeError:
                parsed = raw.decode(errors="replace")
            return exc.code, parsed

    def refresh_csrf(self) -> None:
        for cookie in self.jar:
            if cookie.name == "vip_csrf_token":
                self.csrf = cookie.value


def summarize(value: object) -> str:
    if isinstance(value, dict):
        if "error" in value:
            err = value["error"]
            if isinstance(err, dict):
                return f"ERR {err.get('code')} {err.get('message')}"
            return f"ERR {err}"
        keys = ",".join(list(value)[:8])
        count = None
        for key in ("items", "results", "data", "organizations", "users"):
            if isinstance(value.get(key), list):
                count = f"{key}={len(value[key])}"
                break
        return f"dict[{keys}] {count or ''}".strip()
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return repr(value)[:180]


def main() -> int:
    email = os.environ.get("VIP_PROBE_EMAIL", "")
    password = os.environ.get("VIP_PROBE_PASSWORD", "")
    if not email or not password:
        print("VIP_PROBE_EMAIL and VIP_PROBE_PASSWORD are required", file=sys.stderr)
        return 2

    client = Client()
    status, payload = client.request("POST", "/auth/login", {"email": email, "password": password})
    print(f"LOGIN {status} {summarize(payload)}")
    if status != 200:
        return 1
    client.refresh_csrf()
    if isinstance(payload, dict):
        user = payload.get("user") or {}
        print(
            "USER",
            user.get("email"),
            "platform=",
            user.get("is_platform_admin"),
            "must_change=",
            user.get("must_change_password"),
        )

    status, payload = client.request("GET", "/auth/me")
    print(f"ME {status} {summarize(payload)}")
    status, payload = client.request("GET", "/api/v1/organizations")
    print(f"ORGS {status} {summarize(payload)}")

    if not ORG or not WS:
        print("SKIP tenant matrix: set VIP_PROBE_ORG and VIP_PROBE_WS")
        return 0

    paths = [
        "/api/v1/home/summary",
        "/api/v1/notifications",
        "/api/v1/notifications/unread-count",
        "/api/v1/connections/types",
        "/api/v1/connections",
        "/api/v1/datasets",
        "/api/v1/pipelines",
        "/api/v1/semantic-models",
        "/api/v1/dashboards",
        "/api/v1/jobs",
        "/api/v1/audit-events",
        "/api/v1/usage",
        "/api/v1/reports",
        "/api/v1/insights",
        "/api/v1/marketplace/extensions",
        "/api/v1/ai/assistants",
        "/api/v1/dashboard-deliveries",
    ]
    types: list | None = None
    notifications: list | None = None
    for path in paths:
        status, payload = client.request("GET", path, tenant=True)
        print(f"GET {path} {status} {summarize(payload)}")
        if path.endswith("/connections/types") and isinstance(payload, list):
            types = payload
        if path.endswith("/notifications") and isinstance(payload, list):
            notifications = payload

    if types:
        enabled = [item for item in types if item.get("is_enabled") or item.get("enabled")]
        print("CONNECTOR_COUNT", len(types), "ENABLED", len(enabled))
        for item in types:
            status_name = item.get("implementation_status") or item.get("status")
            if status_name in {"available", "beta"} or item.get("is_enabled"):
                print(
                    "CONNECTOR",
                    item.get("key"),
                    status_name,
                    "enabled=",
                    item.get("is_enabled") or item.get("enabled"),
                )

    if notifications:
        print("NOTIFICATION_COUNT", len(notifications))
        sample = notifications[0]
        print(
            "NOTIFICATION_SAMPLE_CATEGORY",
            sample.get("category"),
            "to=",
            (sample.get("resource") or {}).get("to"),
        )

    status, payload = client.request("GET", "/api/v1/dashboards")
    print(f"DASHBOARDS_NO_TENANT {status} {summarize(payload)}")

    if OTHER_ORG and OTHER_WS:
        req = urllib.request.Request(
            BASE + "/api/v1/dashboards",
            headers={
                "Accept": "application/json",
                "X-CSRF-Token": client.csrf,
                "X-Organization-ID": OTHER_ORG,
                "X-Workspace-ID": OTHER_WS,
            },
            method="GET",
        )
        try:
            with client.opener.open(req, timeout=20) as resp:
                print(
                    "CROSS_TENANT_DASHBOARDS",
                    resp.status,
                    summarize(json.loads(resp.read().decode())),
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode())
            except json.JSONDecodeError:
                parsed = raw.decode(errors="replace")
            print("CROSS_TENANT_DASHBOARDS", exc.code, summarize(parsed))

    if MUTATE:
        status, payload = client.request(
            "POST",
            f"/api/v1/organizations/{ORG}/invitations",
            {
                "email": "certification-probe-invite@example.test",
                "workspace_ids": [WS],
            },
            tenant=True,
        )
        print(f"INVITE {status} {summarize(payload)}")
        if isinstance(payload, dict):
            print("INVITE_HAS_TOKEN", "token" in payload and bool(payload.get("token")))

    viewer_email = os.environ.get("VIP_PROBE_VIEWER_EMAIL", "")
    viewer_password = os.environ.get("VIP_PROBE_VIEWER_PASSWORD", "")
    if viewer_email and viewer_password:
        viewer = Client()
        status, payload = viewer.request(
            "POST", "/auth/login", {"email": viewer_email, "password": viewer_password}
        )
        print(f"VIEWER_LOGIN {status} {summarize(payload)}")
        if status == 200:
            viewer.refresh_csrf()
            status, payload = viewer.request(
                "POST", "/api/v1/pipelines", {"name": "viewer-should-fail"}, tenant=True
            )
            print(f"VIEWER_CREATE_PIPELINE {status} {summarize(payload)}")

    for path in ("/docs", "/openapi.json", "/health", "/ready", "/api/v1/version"):
        req = urllib.request.Request(BASE + path, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"PUBLIC {path} {resp.status} len={len(resp.read())}")
        except urllib.error.HTTPError as exc:
            print(f"PUBLIC {path} {exc.code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
