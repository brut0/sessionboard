#!/usr/bin/env python3
"""SessionBoard Synthetic Health and Availability Probe.

Uses only Python standard library (urllib, json, argparse, time, datetime)
to verify API health, directory entities, and conflict-free booking lifecycle.
Can run in single-shot mode (--mode once) or continuous burst mode (--mode burst).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta


def http_request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, dict, dict]:
    """Perform HTTP request returning (status_code, json_body, response_headers)."""
    hdrs = headers or {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_headers = dict(resp.headers)
            raw = resp.read().decode("utf-8")
            res_body = json.loads(raw) if raw.strip() else {}
            return resp.status, res_body, resp_headers
    except urllib.error.HTTPError as err:
        resp_headers = dict(err.headers)
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
    # 1. Specialists
    status, specialists, _ = http_request(f"{base_url}/api/specialists")
    if status != 200:
        raise RuntimeError(f"Failed to list specialists: status={status}")

    spec = next((s for s in specialists if s.get("name") == "Probe Specialist"), None)
    if not spec:
        status, spec, _ = http_request(
            f"{base_url}/api/specialists",
            method="POST",
            body={"name": "Probe Specialist", "specialty": "Synthetic Probe"},
        )
        if status != 201:
            raise RuntimeError(f"Failed to create probe specialist: status={status}")

    # 2. Clients
    status, clients, _ = http_request(f"{base_url}/api/clients")
    if status != 200:
        raise RuntimeError(f"Failed to list clients: status={status}")

    client = next((c for c in clients if c.get("display_name") == "Probe Client"), None)
    if not client:
        status, client, _ = http_request(
            f"{base_url}/api/clients",
            method="POST",
            body={"display_name": "Probe Client"},
        )
        if status != 201:
            raise RuntimeError(f"Failed to create probe client: status={status}")

    # 3. Rooms
    status, rooms, _ = http_request(f"{base_url}/api/rooms")
    if status != 200:
        raise RuntimeError(f"Failed to list rooms: status={status}")

    room = next((r for r in rooms if r.get("name") == "Probe Room"), None)
    if not room:
        status, room, _ = http_request(
            f"{base_url}/api/rooms",
            method="POST",
            body={"name": "Probe Room"},
        )
        if status != 201:
            raise RuntimeError(f"Failed to create probe room: status={status}")

    return spec["id"], client["id"], room["id"]


def run_single_probe(base_url: str, spec_id: int, client_id: int, room_id: int, offset_days: int = 400) -> bool:
    """Execute one probe booking lifecycle (create -> cancel). Returns True if passed."""
    # Target date 400 days ahead to stay clear of operational bookings
    target_date = (date.today() + timedelta(days=offset_days)).isoformat()
    start_time = "11:00"
    duration = 60

    # 1. Book session
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

    if status != 201:
        print(f"[FAIL] POST /api/sessions returned status={status} (trace_id={trace_id}): {session}")
        return False

    session_id = session.get("id")
    print(f"[OK] Created probe session #{session_id} on {target_date} (trace_id={trace_id})")

    # 2. Cancel session
    cancel_status, cancel_body, _ = http_request(
        f"{base_url}/api/sessions/{session_id}",
        method="PATCH",
        body={"status": "cancelled"},
    )
    if cancel_status != 200 or cancel_body.get("status") != "cancelled":
        print(f"[FAIL] PATCH /api/sessions/{session_id} returned status={cancel_status}: {cancel_body}")
        return False

    print(f"[OK] Cancelled probe session #{session_id} successfully")
    return True


def run_probe_suite(base_url: str, mode: str, burst_minutes: int) -> int:
    """Run synthetic probe in once or burst mode. Returns exit code (0 = success)."""
    base_url = base_url.rstrip("/")
    print(f"Starting SessionBoard synthetic probe against: {base_url} (mode={mode})")

    # Check health
    status, health, _ = http_request(f"{base_url}/api/health")
    if status != 200 or health.get("status") != "ok":
        print(f"[FAIL] /api/health probe failed: status={status}, response={health}")
        return 1
    print(f"[OK] /api/health healthy: {health}")

    # Check version
    status, version_info, _ = http_request(f"{base_url}/api/version")
    if status == 200:
        print(f"[OK] /api/version: version={version_info.get('version')} env={version_info.get('env')}")

    # Ensure probe entities
    try:
        spec_id, client_id, room_id = ensure_probe_entities(base_url)
        print(f"[OK] Probe entities confirmed (spec={spec_id}, client={client_id}, room={room_id})")
    except Exception as err:
        print(f"[FAIL] Entity setup failed: {err}")
        return 1

    if mode == "once":
        iterations = 3
        success_count = 0
        for i in range(iterations):
            # Use different offset days to test multiple future slots
            if run_single_probe(base_url, spec_id, client_id, room_id, offset_days=400 + i):
                success_count += 1
            time.sleep(0.5)

        print(f"\nProbe summary: {success_count}/{iterations} successful lifecycles")
        return 0 if success_count == iterations else 1

    elif mode == "burst":
        end_time = time.time() + (burst_minutes * 60)
        iteration = 0
        success_count = 0
        failure_count = 0
        print(f"Running burst mode for {burst_minutes} minutes...")

        while time.time() < end_time:
            iteration += 1
            if run_single_probe(base_url, spec_id, client_id, room_id, offset_days=400 + (iteration % 30)):
                success_count += 1
            else:
                failure_count += 1
            time.sleep(2)

        print(f"\nBurst summary: total={iteration}, success={success_count}, failures={failure_count}")
        return 0 if failure_count == 0 else 1

    else:
        print(f"Unknown mode: {mode}")
        return 2


def main():
    parser = argparse.ArgumentParser(description="SessionBoard Synthetic Health & Booking Probe")
    parser.add_argument("--base-url", default="http://localhost:8000", help="SessionBoard base URL")
    parser.add_argument("--mode", choices=["once", "burst"], default="once", help="Probe run mode")
    parser.add_argument("--minutes", type=int, default=15, help="Burst mode duration in minutes")
    args = parser.parse_args()

    sys.exit(run_probe_suite(args.base_url, args.mode, args.minutes))


if __name__ == "__main__":
    main()
