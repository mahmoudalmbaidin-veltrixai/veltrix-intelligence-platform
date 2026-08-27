"""Pre-demo live journey probe. Prints statuses only. Never prints secrets."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("VIP_PROBE_BASE", "http://localhost:8000").rstrip("/")
ORG = os.environ["VIP_PROBE_ORG"]
WS = os.environ["VIP_PROBE_WS"]
OTHER_ORG = os.environ.get("VIP_PROBE_OTHER_ORG", "")
OTHER_WS = os.environ.get("VIP_PROBE_OTHER_WS", "")
CONN = os.environ.get("VIP_PROBE_CONNECTION", "")
DATASET = os.environ.get("VIP_PROBE_DATASET", "")
PIPELINE = os.environ.get("VIP_PROBE_PIPELINE", "")
SEMANTIC = os.environ.get("VIP_PROBE_SEMANTIC", "")
DASHBOARD = os.environ.get("VIP_PROBE_DASHBOARD", "")
FOREIGN_DASH = os.environ.get("VIP_PROBE_FOREIGN_DASHBOARD", "")


class Client:
    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        tenant: bool = False,
        org: str | None = None,
        ws: str | None = None,
        timeout: int = 30,
    ) -> tuple[int, object]:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if tenant:
            headers["X-Organization-ID"] = org or ORG
            headers["X-Workspace-ID"] = ws or WS
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode()) if raw else None
                return resp.status, parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode()) if raw else None
            except json.JSONDecodeError:
                parsed = raw.decode(errors="replace")[:300]
            return exc.code, parsed

    def refresh_csrf(self) -> None:
        for cookie in self.jar:
            if cookie.name == "vip_csrf_token":
                self.csrf = cookie.value


def summarize(value: object) -> str:
    if isinstance(value, dict):
        err = value.get("error")
        if isinstance(err, dict):
            return f"ERR {err.get('code')} {err.get('message')}"
        keys = ",".join(list(value)[:10])
        for key in ("items", "results", "data", "nodes", "widgets", "pages"):
            if isinstance(value.get(key), list):
                return f"dict[{keys}] {key}={len(value[key])}"
        return f"dict[{keys}]"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return repr(value)[:200]


def login(email: str, password: str) -> tuple[Client, int, object]:
    client = Client()
    status, payload = client.request("POST", "/auth/login", {"email": email, "password": password})
    if status == 200:
        client.refresh_csrf()
    return client, status, payload


def main() -> int:
    email = os.environ["VIP_PROBE_EMAIL"]
    password = os.environ["VIP_PROBE_PASSWORD"]
    viewer_email = os.environ.get("VIP_PROBE_VIEWER_EMAIL", "")
    viewer_password = os.environ.get("VIP_PROBE_VIEWER_PASSWORD", "")
    platform_email = os.environ.get("VIP_PROBE_PLATFORM_EMAIL", "")
    platform_password = os.environ.get("VIP_PROBE_PLATFORM_PASSWORD", "")

    print("=== INVALID LOGIN ===")
    bad, status, payload = login("northstar.org.admin@example.com", "definitely-wrong-password")
    print(f"BAD_PASSWORD {status} {summarize(payload)}")
    missing, status, payload = login("does-not-exist@example.com", "x")
    print(f"UNKNOWN_USER {status} {summarize(payload)}")

    print("=== JOURNEY A ADMIN LOGIN ===")
    admin, status, payload = login(email, password)
    print(f"LOGIN {status} {summarize(payload)}")
    if status != 200:
        return 1
    user = payload.get("user") if isinstance(payload, dict) else {}
    print(
        "USER",
        user.get("email"),
        "platform=",
        user.get("is_platform_admin"),
        "must_change=",
        user.get("must_change_password"),
    )
    status, payload = admin.request("GET", "/auth/me")
    print(f"ME {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/organizations")
    print(f"ORGS {status} {summarize(payload)}")
    status, payload = admin.request("GET", f"/api/v1/organizations/{ORG}/workspaces", tenant=True)
    print(f"WORKSPACES {status} {summarize(payload)}")
    status, payload = admin.request("GET", f"/api/v1/organizations/{ORG}/members", tenant=True)
    print(f"MEMBERS {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/roles", tenant=True)
    print(f"ROLES {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/platform/organizations")
    print(f"PLATFORM_ORGS_AS_ORG_ADMIN {status} {summarize(payload)}")

    print("=== JOURNEY B ANALYST PATH ===")
    if CONN:
        status, payload = admin.request("GET", f"/api/v1/connections/{CONN}", tenant=True)
        print(f"CONNECTION {status} {summarize(payload)}")
        if isinstance(payload, dict):
            print(
                "CONNECTION_HEALTH",
                payload.get("health_status"),
                "test=",
                payload.get("last_test_status"),
                "type=",
                (payload.get("type") or {}).get("key"),
            )
        status, payload = admin.request("POST", f"/api/v1/connections/{CONN}/test", {}, tenant=True)
        print(f"CONNECTION_TEST {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/connections/types", tenant=True)
    print(f"CONNECTION_TYPES {status} {summarize(payload)}")
    if isinstance(payload, list):
        enabled = [t for t in payload if t.get("is_enabled")]
        leftover = [t["key"] for t in payload if str(t.get("key", "")).startswith("pg-")]
        by_status: dict[str, list[str]] = {}
        for item in payload:
            by_status.setdefault(str(item.get("implementation_status")), []).append(item["key"])
        print("CONNECTOR_ENABLED", sorted(t["key"] for t in enabled))
        print("CONNECTOR_STATUS_COUNTS", {k: len(v) for k, v in sorted(by_status.items())})
        print("CONNECTOR_LEFTOVER_PG", leftover[:20], "count=", len(leftover))
        for key in ("postgresql", "local_file", "mysql", "mssql", "snowflake", "bigquery", "s3", "rest_api"):
            match = next((t for t in payload if t["key"] == key), None)
            if match:
                print(
                    "CONNECTOR",
                    key,
                    "status=",
                    match.get("implementation_status"),
                    "enabled=",
                    match.get("is_enabled"),
                    "caps=",
                    match.get("capabilities"),
                )

    if DATASET:
        status, payload = admin.request("GET", f"/api/v1/datasets/{DATASET}", tenant=True)
        print(f"DATASET {status} {summarize(payload)}")
        t0 = time.perf_counter()
        status, payload = admin.request("GET", f"/api/v1/datasets/{DATASET}/preview", tenant=True)
        print(f"PREVIEW {status} {summarize(payload)} ms={int((time.perf_counter()-t0)*1000)}")
        if isinstance(payload, dict):
            print(
                "PREVIEW_ROWS",
                len(payload.get("rows") or payload.get("items") or []),
                "columns=",
                len(payload.get("columns") or []),
            )
        t0 = time.perf_counter()
        status, payload = admin.request("GET", f"/api/v1/datasets/{DATASET}/quality", tenant=True)
        print(f"QUALITY {status} {summarize(payload)} ms={int((time.perf_counter()-t0)*1000)}")
        if isinstance(payload, dict):
            print(
                "QUALITY_SCORE",
                payload.get("score") or payload.get("overall_score") or payload.get("quality_score"),
                "keys=",
                list(payload)[:12],
            )
        status, payload = admin.request(
            "GET", f"/api/v1/datasets/{DATASET}/quality-evaluations", tenant=True
        )
        print(f"QUALITY_EVALS {status} {summarize(payload)}")

    if PIPELINE:
        status, payload = admin.request("GET", f"/api/v1/pipelines/{PIPELINE}", tenant=True)
        print(f"PIPELINE {status} {summarize(payload)}")
        nodes = []
        if isinstance(payload, dict):
            nodes = payload.get("nodes") or (payload.get("pipeline") or {}).get("nodes") or []
            print("PIPELINE_NODE_COUNT", len(nodes) if isinstance(nodes, list) else "n/a")
            if isinstance(nodes, list):
                kinds = [n.get("type") or n.get("kind") for n in nodes]
                print("PIPELINE_NODE_TYPES", kinds)
        status, payload = admin.request("GET", f"/api/v1/pipelines/{PIPELINE}/runs", tenant=True)
        print(f"PIPELINE_RUNS {status} {summarize(payload)}")
        status, payload = admin.request(
            "POST", f"/api/v1/pipelines/{PIPELINE}/runs", {}, tenant=True, timeout=60
        )
        print(f"PIPELINE_RUN_CREATE {status} {summarize(payload)}")
        run_id = payload.get("id") if isinstance(payload, dict) else None
        if run_id:
            for _ in range(24):
                time.sleep(5)
                st, run = admin.request(
                    "GET", f"/api/v1/pipelines/{PIPELINE}/runs/{run_id}", tenant=True
                )
                run_status = run.get("status") if isinstance(run, dict) else None
                print(f"PIPELINE_RUN_POLL {st} status={run_status}")
                if run_status in {"succeeded", "failed", "cancelled"}:
                    print(f"PIPELINE_RUN_FINAL {summarize(run)}")
                    break

    if SEMANTIC:
        status, payload = admin.request("GET", f"/api/v1/semantic-models/{SEMANTIC}", tenant=True)
        print(f"SEMANTIC {status} {summarize(payload)}")
        if isinstance(payload, dict):
            print("SEMANTIC_STATUS", payload.get("status"), "version=", payload.get("version"))

    if DASHBOARD:
        status, payload = admin.request("GET", f"/api/v1/dashboards/{DASHBOARD}", tenant=True)
        print(f"DASHBOARD {status} {summarize(payload)}")
        status, payload = admin.request(
            "GET", f"/api/v1/dashboards/{DASHBOARD}/viewer", tenant=True, timeout=60
        )
        print(f"DASHBOARD_VIEWER {status} {summarize(payload)}")
        if isinstance(payload, dict):
            pages = payload.get("pages") or (payload.get("snapshot") or {}).get("pages") or []
            widgets = []
            for page in pages if isinstance(pages, list) else []:
                widgets.extend(page.get("widgets") or [])
            print("DASHBOARD_WIDGETS", [w.get("type") or w.get("widget_type") for w in widgets])
        t0 = time.perf_counter()
        status, payload = admin.request(
            "POST",
            f"/api/v1/dashboards/{DASHBOARD}/exports",
            {"format": "pdf", "timezone": "Asia/Riyadh"},
            tenant=True,
        )
        print(f"EXPORT_PDF {status} {summarize(payload)} ms={int((time.perf_counter()-t0)*1000)}")
        pdf_id = payload.get("id") if isinstance(payload, dict) else None
        t0 = time.perf_counter()
        status, payload = admin.request(
            "POST",
            f"/api/v1/dashboards/{DASHBOARD}/exports",
            {"format": "png", "timezone": "Asia/Riyadh"},
            tenant=True,
        )
        print(f"EXPORT_PNG {status} {summarize(payload)} ms={int((time.perf_counter()-t0)*1000)}")
        png_id = payload.get("id") if isinstance(payload, dict) else None
        for label, export_id in (("PDF", pdf_id), ("PNG", png_id)):
            if not export_id:
                continue
            for _ in range(24):
                time.sleep(3)
                st, exp = admin.request("GET", f"/api/v1/dashboard-exports/{export_id}", tenant=True)
                exp_status = exp.get("status") if isinstance(exp, dict) else None
                print(f"EXPORT_{label}_POLL {st} status={exp_status}")
                if exp_status in {"completed", "failed", "cancelled"}:
                    print(f"EXPORT_{label}_FINAL {summarize(exp)}")
                    break

    print("=== JOURNEY C VIEWER ===")
    if viewer_email and viewer_password:
        viewer, status, payload = login(viewer_email, viewer_password)
        print(f"VIEWER_LOGIN {status} {summarize(payload)}")
        if status == 200:
            if DASHBOARD:
                status, payload = viewer.request(
                    "GET", f"/api/v1/dashboards/{DASHBOARD}/viewer", tenant=True, timeout=60
                )
                print(f"VIEWER_DASHBOARD {status} {summarize(payload)}")
                status, payload = viewer.request(
                    "PUT",
                    f"/api/v1/dashboards/{DASHBOARD}/editor",
                    {"name": "viewer-should-fail"},
                    tenant=True,
                )
                print(f"VIEWER_EDIT {status} {summarize(payload)}")
            status, payload = viewer.request(
                "POST", "/api/v1/pipelines", {"name": "viewer-should-fail"}, tenant=True
            )
            print(f"VIEWER_CREATE_PIPELINE {status} {summarize(payload)}")
            if FOREIGN_DASH and OTHER_ORG and OTHER_WS:
                status, payload = viewer.request(
                    "GET",
                    f"/api/v1/dashboards/{FOREIGN_DASH}/viewer",
                    tenant=True,
                    org=OTHER_ORG,
                    ws=OTHER_WS,
                )
                print(f"VIEWER_FOREIGN_WITH_HEADERS {status} {summarize(payload)}")
                status, payload = viewer.request(
                    "GET", f"/api/v1/dashboards/{FOREIGN_DASH}/viewer", tenant=True
                )
                print(f"VIEWER_FOREIGN_OWN_TENANT {status} {summarize(payload)}")

    print("=== JOURNEY D NOTIFICATIONS ===")
    status, payload = admin.request("GET", "/api/v1/notifications", tenant=True)
    print(f"NOTIFICATIONS {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/notifications/unread-count", tenant=True)
    print(f"UNREAD {status} {summarize(payload)}")
    status, payload = admin.request("GET", "/api/v1/notifications", tenant=True)
    sample_id = None
    sample_to = None
    if isinstance(payload, list) and payload:
        sample_id = payload[0].get("id")
        sample_to = (payload[0].get("resource") or {}).get("to")
        print(
            "NOTIFICATION_SAMPLE",
            payload[0].get("title"),
            "category=",
            payload[0].get("category"),
            "read=",
            payload[0].get("read"),
            "to=",
            sample_to,
        )
    if sample_id:
        status, payload = admin.request(
            "POST", f"/api/v1/notifications/{sample_id}/read", {}, tenant=True
        )
        print(f"MARK_READ {status} {summarize(payload)}")
        status, payload = admin.request("GET", "/api/v1/notifications/unread-count", tenant=True)
        print(f"UNREAD_AFTER_ONE {status} {summarize(payload)}")
        status, payload = admin.request("POST", "/api/v1/notifications/read-all", {}, tenant=True)
        print(f"MARK_ALL {status} {summarize(payload)}")
        status, payload = admin.request("GET", "/api/v1/notifications/unread-count", tenant=True)
        print(f"UNREAD_AFTER_ALL {status} {summarize(payload)}")
        relogin, status, _ = login(email, password)
        if status == 200:
            status, payload = relogin.request("GET", "/api/v1/notifications/unread-count", tenant=True)
            print(f"UNREAD_AFTER_RELOGIN {status} {summarize(payload)}")
        admin = relogin if status == 200 else admin
        admin.refresh_csrf()

    print("=== JOURNEY E SCHEDULING ===")
    status, payload = admin.request("GET", "/api/v1/dashboard-deliveries", tenant=True)
    print(f"DELIVERIES {status} {summarize(payload)}")
    if isinstance(payload, list):
        for item in payload:
            print(
                "DELIVERY",
                item.get("name"),
                "enabled=",
                item.get("enabled"),
                "status=",
                item.get("status"),
                "tz=",
                item.get("timezone"),
                "next=",
                item.get("next_run_at"),
            )
    if PIPELINE:
        status, payload = admin.request("GET", f"/api/v1/pipelines/{PIPELINE}/schedules", tenant=True)
        print(f"PIPELINE_SCHEDULES {status} {summarize(payload)}")

    print("=== SECURITY / IDOR ===")
    if DASHBOARD:
        status, payload = admin.request("GET", f"/api/v1/dashboards/{DASHBOARD}")
        print(f"DASHBOARD_NO_TENANT {status} {summarize(payload)}")
    if FOREIGN_DASH and OTHER_ORG and OTHER_WS:
        status, payload = admin.request(
            "GET",
            f"/api/v1/dashboards/{FOREIGN_DASH}",
            tenant=True,
            org=OTHER_ORG,
            ws=OTHER_WS,
        )
        print(f"CROSS_TENANT_DASHBOARD {status} {summarize(payload)}")
        status, payload = admin.request(
            "GET", "/api/v1/dashboards", tenant=True, org=OTHER_ORG, ws=OTHER_WS
        )
        print(f"CROSS_TENANT_LIST {status} {summarize(payload)}")

    print("=== GATED / PLACEHOLDER MODULES ===")
    for path in (
        "/api/v1/reports",
        "/api/v1/insights",
        "/api/v1/marketplace/extensions",
        "/api/v1/ai/assistants",
        "/api/v1/usage",
        "/api/v1/audit-events",
        "/api/v1/home/summary",
        "/api/v1/jobs",
    ):
        status, payload = admin.request("GET", path, tenant=True)
        print(f"GET {path} {status} {summarize(payload)}")

    print("=== PLATFORM ADMIN ===")
    if platform_email and platform_password:
        plat, status, payload = login(platform_email, platform_password)
        print(f"PLATFORM_LOGIN {status} {summarize(payload)}")
        if status == 200:
            status, payload = plat.request("GET", "/api/v1/platform/organizations")
            print(f"PLATFORM_ORGS {status} {summarize(payload)}")
            status, payload = plat.request("GET", "/api/v1/platform/users?page=1&page_size=50")
            print(f"PLATFORM_USERS {status} {summarize(payload)}")

    print("=== PASSWORD RESET REQUEST (file outbox) ===")
    anon = Client()
    status, payload = anon.request(
        "POST", "/auth/password-reset/request", {"identifier": email}
    )
    print(f"PASSWORD_RESET_REQUEST {status} {summarize(payload)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
