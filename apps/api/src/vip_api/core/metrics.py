"""Small dependency-free Prometheus registry for process-local API metrics."""

from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsRegistry:
    """Collect bounded, non-tenant process metrics safe for a global scrape."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active_requests = 0
        self._requests: Counter[tuple[str, int]] = Counter()
        self._duration_count = 0
        self._duration_sum = 0.0
        self._authentication_failures = 0
        self._rate_limit_events = 0
        self._database_healthy = 0
        self._redis_healthy = 0
        self._sse_active = 0
        self._sse_resume_attempts = 0
        self._sse_reconnects = 0
        self._sse_missed_event_recoveries = 0
        self._sse_dropped_events = 0
        self._sse_stream_errors = 0

    def request_started(self) -> None:
        with self._lock:
            self._active_requests += 1

    def request_finished(self, method: str, status_code: int, duration_seconds: float) -> None:
        method = (
            method.upper()
            if method.upper() in {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
            else "OTHER"
        )
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._requests[(method, status_code)] += 1
            self._duration_count += 1
            self._duration_sum += duration_seconds
            if status_code == 429:
                self._rate_limit_events += 1

    def authentication_failed(self) -> None:
        with self._lock:
            self._authentication_failures += 1

    def dependencies(self, *, database: bool, redis: bool) -> None:
        with self._lock:
            self._database_healthy = int(database)
            self._redis_healthy = int(redis)

    def sse_opened(self, *, resumed: bool) -> None:
        with self._lock:
            self._sse_active += 1
            if resumed:
                self._sse_resume_attempts += 1
                self._sse_reconnects += 1

    def sse_closed(self) -> None:
        with self._lock:
            self._sse_active = max(0, self._sse_active - 1)

    def sse_missed_event_recovered(self) -> None:
        with self._lock:
            self._sse_missed_event_recoveries += 1

    def sse_dropped(self) -> None:
        with self._lock:
            self._sse_dropped_events += 1

    def sse_error(self) -> None:
        with self._lock:
            self._sse_stream_errors += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP vip_http_requests_total HTTP requests by bounded method and status.",
                "# TYPE vip_http_requests_total counter",
            ]
            for (method, status_code), value in sorted(self._requests.items()):
                lines.append(
                    f'vip_http_requests_total{{method="{method}",status="{status_code}"}} {value}'
                )
            lines.extend(
                [
                    "# TYPE vip_http_request_duration_seconds summary",
                    f"vip_http_request_duration_seconds_count {self._duration_count}",
                    f"vip_http_request_duration_seconds_sum {self._duration_sum:.9f}",
                    "# TYPE vip_http_active_requests gauge",
                    f"vip_http_active_requests {self._active_requests}",
                    "# TYPE vip_authentication_failures_total counter",
                    f"vip_authentication_failures_total {self._authentication_failures}",
                    "# TYPE vip_rate_limit_events_total counter",
                    f"vip_rate_limit_events_total {self._rate_limit_events}",
                    "# TYPE vip_database_healthy gauge",
                    f"vip_database_healthy {self._database_healthy}",
                    "# TYPE vip_redis_healthy gauge",
                    f"vip_redis_healthy {self._redis_healthy}",
                    "# TYPE vip_sse_active_connections gauge",
                    f"vip_sse_active_connections {self._sse_active}",
                    "# TYPE vip_sse_resume_attempts_total counter",
                    f"vip_sse_resume_attempts_total {self._sse_resume_attempts}",
                    "# TYPE vip_sse_reconnects_total counter",
                    f"vip_sse_reconnects_total {self._sse_reconnects}",
                    "# TYPE vip_sse_missed_event_recoveries_total counter",
                    f"vip_sse_missed_event_recoveries_total {self._sse_missed_event_recoveries}",
                    "# TYPE vip_sse_dropped_events_total counter",
                    f"vip_sse_dropped_events_total {self._sse_dropped_events}",
                    "# TYPE vip_sse_stream_errors_total counter",
                    f"vip_sse_stream_errors_total {self._sse_stream_errors}",
                ]
            )
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
