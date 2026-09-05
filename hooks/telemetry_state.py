#!/usr/bin/env python3
"""Record in-session ThemeMate telemetry (mode/feature/usecase/outcome).

Called by Claude during a ThemeMate session (see skills/thememate/SKILL.md)
whenever mode/feature/usecase becomes known or the task reaches a stopping
point. Writes to a per-session state file that telemetry-hook.py reads and
attaches to the session_end event, then deletes.

Also sends a session_heartbeat event with whatever state is known so far --
mode/feature/usecase/outcome would otherwise only ever reach the server at
session_end, which for a long-running session may not happen for a while (or,
mid-conversation, at all). The heartbeat carries the same session_id as the
session_start/session_end events so the server merges it into that one
session document instead of creating a separate row.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telemetry_common import (
    SESSIONS_DIR,
    SESSION_ID_RE,
    atomic_write,
    install_id,
    send_event,
    skill_version,
)

FIELDS = (
    "mode",
    "feature",
    "usecase",
    "usecase_met",
    "outcome",
    "failure_category",
    "summary",
    "role",
    "agency_name",
    "merchant_store_url",
    "demo_store_url",
)


def state_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def build_heartbeat(session_id: str, state: dict) -> dict:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "session_heartbeat",
        "install_id": install_id(),
        "session_id": session_id,
        "skill": "thememate",
        "skill_version": skill_version(),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "skill",
        "schema_version": 1,
    }
    for field in FIELDS:
        value = state.get(field)
        if value is None:
            continue
        payload[field] = value.upper() if field == "mode" else value
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["set"])
    parser.add_argument("--session-id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    parser.add_argument("--mode", choices=["ask", "inspect", "edit"])
    parser.add_argument("--feature")
    parser.add_argument("--usecase")
    parser.add_argument("--usecase-met", dest="usecase_met", choices=["yes", "no"])
    parser.add_argument("--outcome", choices=["completed", "blocked", "error", "scope_rejected"])
    parser.add_argument("--failure-category", dest="failure_category")
    parser.add_argument("--summary")
    parser.add_argument("--role", choices=["internal", "agency", "merchant", "support", "unknown"])
    parser.add_argument("--agency", dest="agency_name")
    parser.add_argument("--store", dest="merchant_store_url")
    parser.add_argument("--demo-store", dest="demo_store_url")
    args = parser.parse_args()

    # Called silently by the skill mid-session (see SKILL.md) -- never print or
    # exit non-zero for a missing/invalid session id, just no-op.
    if not args.session_id or not SESSION_ID_RE.fullmatch(args.session_id):
        return 0

    try:
        path = state_path(args.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        path.parent.parent.chmod(0o700)
        current = {}
        if path.exists():
            try:
                current = json.loads(path.read_text())
            except Exception:
                current = {}
        for field in FIELDS:
            value = getattr(args, field)
            if value is not None:
                current[field] = value
        atomic_write(path, json.dumps(current), 0o600)
    except Exception:
        return 0

    send_event(build_heartbeat(args.session_id, current))
    return 0


if __name__ == "__main__":
    sys.exit(main())
