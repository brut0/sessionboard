#!/usr/bin/env python3
"""SessionBoard Synthetic Health and Availability Probe.

Uses only Python standard library modules to verify API health, directory entities,
and conflict-free booking lifecycle across deterministic 15-minute aligned slots.
Every third iteration schedules at :45 with a 30-minute duration to exercise hour
rollover behavior without datetime.time minute-overflow errors.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

SLOT_TEMPLATES: tuple[tuple[str, int], ...] = (
    ("08:00", 30),
    ("09:15", 30),
    ("10:45", 30),
    ("12:00", 30),
    ("13:15", 30),
    ("14:45", 30),
)


@dataclass
class ProbeStats:
    """Counters for synthetic booking iterations and HTTP outcome classes."""

    total: int = 0
    created_2xx: int = 0
    client_4xx: int = 0
    error_5xx: int = 0
    cancel_failed: int = 0


def select_probe_slot(iteration: int) -> tuple[int, str, int]:
    """Return (offset_days, start_time, duration_minutes) for a 1-based iteration.

    Uses dates >= 400 days in the future and 6 non-overlapping daily slots so
    consecutive probes never collide. Iterations divisible by 3 always pick a
    :45 start time with 30-minute duration.
    """
    idx = max(iteration - 1, 0)
    offset_days = 400 + (idx // len(SLOT_TEMPLATES))
    start_time, duration_minutes = SLOT_TEMPLATES[idx % len(SLOT_TEMPLATES)]
    return offset_days, start_time, duration_minutes


def http_request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, dict | list, dict]:
    """Perform HTTP request returning (status_code, json_body, response_headers)."""
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            raw = resp.read().decode("utf-8")
            res_body = json.loads(raw) if raw.strip() else {}
            return resp.status, res_body, resp_headers
    except urllib.error.HTTPError as err:
        resp_headers = {k.lower(): v for k, v in err.headers.items()}
        raw = err.read().decode("utf-8")
        try:
            res_body = json.loads(raw) if raw.strip() else {}
        except Exception:
            res_body = {"detail": raw}
        return err.code, res_body, resp_headers
    except Exception as err:
        return 599, {"detail": str(err)}, {}


def ensure_probe_entities(base_url: str) -> tuple[int, int, int]:
    """Ensure probe specialist, client, and room exist and return (spec_id, client_id, room_id)."""
    status, specialists, _ = http_request(f"{base_url}/api/specialists")
    if status != 200 or not isinstance(specialists, list):
        raise RuntimeError(f"Failed to list specialists: status={status}")

    spec = next((s for s in specialists if s.get("name") == "Probe Specialist"), None)
    if not spec:
        status, spec, _ = http_request(
            f"{base_url}/api/specialists",
            method="POST",
            body={"name": "Probe Specialist", "specialty": "Synthetic Probe"},
        )
        if status != 201 or not isinstance(spec, dict):
            raise RuntimeError(f"Failed to create probe specialist: status={status}")

    status, clients, _ = http_request(f"{base_url}/api/clients")
    if status != 200 or not isinstance(clients, list):
        raise RuntimeError(f"Failed to list clients: status={status}")

    client = next((c for c in clients if c.get("display_name") == "Probe Client"), None)
    if not client:
        status, client, _ = http_request(
            f"{base_url}/api/clients",
            method="POST",
            body={"display_name": "Probe Client"},
        )
        if status != 201 or not isinstance(client, dict):
            raise RuntimeError(f"Failed to create probe client: status={status}")

    status, rooms, _ = http_request(f"{base_url}/api/rooms")
    if status != 200 or not isinstance(rooms, list):
        raise RuntimeError(f"Failed to list rooms: status={status}")

    room = next((r for r in rooms if r.get("name") == "Probe Room"), None)
    if not room:
        status, room, _ = http_request(
            f"{base_url}/api/rooms",
            method="POST",
            body={"name": "Probe Room"},
        )
        if status != 201 or not isinstance(room, dict):
            raise RuntimeError(f"Failed to create probe room: status={status}")

    return int(spec["id"]), int(client["id"]), int(room["id"])


def wait_for_health(
    base_url: str,
    attempts: int = 6,
    sleep_seconds: float = 15.0,
) -> tuple[int, dict]:
    """Check /api/health with brief retries for free-tier container cold starts."""
    last_status = 599
    last_body: dict = {}
    for attempt in range(attempts):
        status, body, _ = http_request(f"{base_url}/api/health")
        last_status = status
        last_body = body if isinstance(body, dict) else {"detail": str(body)}
        if status == 200 and last_body.get("status") == "ok":
            return status, last_body
        if attempt + 1 < attempts and sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return last_status, last_body


def run_single_probe(
    base_url: str,
    spec_id: int,
    client_id: int,
    room_id: int,
    *,
    iteration: int = 1,
    stats: ProbeStats | None = None,
) -> bool:
    """Execute one booking -> cancel lifecycle. Updates stats and returns True if healthy."""
    tracker = stats if stats is not None else ProbeStats()
    tracker.total += 1

    offset_days, start_time, duration = select_probe_slot(iteration)
    target_date = (date.today() + timedelta(days=offset_days)).isoformat()

    book_body = {
        "specialist_id": spec_id,
        "client_id": client_id,
        "room_id": room_id,
        "session_date": target_date,
        "start_time": start_time,
        "duration_minutes": duration,
    }
    status, session, hdrs = http_request(f"{base_url}/api/sessions", method="POST", body=book_body)
    trace_id = hdrs.get("x-trace-id", "unknown")

    if status != 201 or not isinstance(session, dict):
        if status >= 500:
            tracker.error_5xx += 1
        elif 400 <= status < 500:
            tracker.client_4xx += 1
        else:
            tracker.error_5xx += 1
        print(
            f"[FAIL] iter={iteration} POST /api/sessions ({target_date} {start_time}+{duration}m) "
            f"status={status} trace_id={trace_id}: {session}"
        )
        return False

    tracker.created_2xx += 1
    session_id = session.get("id")
    print(
        f"[OK] iter={iteration} created session #{session_id} "
        f"({target_date} {start_time}+{duration}m, trace_id={trace_id})"
    )

    cancel_status, cancel_body, _ = http_request(
        f"{base_url}/api/sessions/{session_id}",
        method="PATCH",
        body={"status": "cancelled"},
    )
    if (
        cancel_status != 200
        or not isinstance(cancel_body, dict)
        or cancel_body.get("status") != "cancelled"
    ):
        tracker.cancel_failed += 1
        if cancel_status >= 500:
            tracker.error_5xx += 1
        print(f"[FAIL] PATCH /api/sessions/{session_id} status={cancel_status}: {cancel_body}")
        return False

    print(f"[OK] Cancelled probe session #{session_id}")
    return True


def run_probe_suite(
    base_url: str,
    mode: str,
    burst_minutes: int,
    interval_seconds: float = 10.0,
) -> int:
    """Run synthetic probe in once or burst mode. Returns 1 if any 5xx or setup failure occurred."""
    base_url = base_url.rstrip("/")
    print(f"Starting SessionBoard synthetic probe against: {base_url} (mode={mode})")

    status, health = wait_for_health(base_url)
    if status != 200 or health.get("status") != "ok":
        print(f"[FAIL] /api/health probe failed: status={status}, response={health}")
        return 1
    print(f"[OK] /api/health healthy: {health}")

    status, version_info, _ = http_request(f"{base_url}/api/version")
    if status == 200 and isinstance(version_info, dict):
        ver = version_info.get("version")
        env_name = version_info.get("env")
        print(f"[OK] /api/version: version={ver} env={env_name}")

    try:
        spec_id, client_id, room_id = ensure_probe_entities(base_url)
        print(f"[OK] Probe entities confirmed (spec={spec_id}, client={client_id}, room={room_id})")
    except Exception as err:
        print(f"[FAIL] Entity setup failed: {err}")
        return 1

    stats = ProbeStats()
    if mode == "once":
        iterations = 3
        for iteration in range(1, iterations + 1):
            run_single_probe(
                base_url,
                spec_id,
                client_id,
                room_id,
                iteration=iteration,
                stats=stats,
            )
            if iteration < iterations:
                time.sleep(0.5)

        print(
            f"\nProbe summary: total={stats.total}, 2xx={stats.created_2xx}, "
            f"4xx={stats.client_4xx}, 5xx={stats.error_5xx}, cancel_failed={stats.cancel_failed}"
        )
        all_ok = stats.error_5xx == 0 and stats.client_4xx == 0 and stats.cancel_failed == 0
        return 0 if all_ok else 1

    if mode == "burst":
        end_time = time.time() + (burst_minutes * 60)
        iteration = 0
        print(f"Running burst mode for {burst_minutes} minutes (interval={interval_seconds}s)...")

        while time.time() < end_time:
            iteration += 1
            run_single_probe(
                base_url,
                spec_id,
                client_id,
                room_id,
                iteration=iteration,
                stats=stats,
            )
            if interval_seconds > 0 and time.time() < end_time:
                time.sleep(interval_seconds)

        print(
            f"\nBurst summary: total={stats.total}, 2xx={stats.created_2xx}, "
            f"4xx={stats.client_4xx}, 5xx={stats.error_5xx}, cancel_failed={stats.cancel_failed}"
        )
        return 0 if stats.error_5xx == 0 and stats.cancel_failed == 0 else 1

    print(f"Unknown mode: {mode}")
    return 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the synthetic probe."""
    parser = argparse.ArgumentParser(description="SessionBoard Synthetic Health & Booking Probe")
    parser.add_argument("--base-url", default="http://localhost:8000", help="SessionBoard base URL")
    parser.add_argument("--mode", choices=["once", "burst"], default="once", help="Probe run mode")
    parser.add_argument("--minutes", type=int, default=15, help="Burst mode duration in minutes")
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds between iterations in burst mode (default: 10.0)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    sys.exit(run_probe_suite(args.base_url, args.mode, args.minutes, args.interval))


if __name__ == "__main__":
    main()
