#!/usr/bin/env python3
"""Record in-session ThemeMate telemetry (mode/feature/usecase/outcome).

Called by Claude during a ThemeMate session (see skills/thememate/SKILL.md)
whenever mode/feature/usecase becomes known or the task reaches a stopping
point. Writes to a per-session state file that telemetry-hook.py reads and
attaches to the session_end event, then deletes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / ".thememate-telemetry" / "sessions"

FIELDS = (
    "mode",
    "feature",
    "usecase",
    "usecase_met",
    "outcome",
    "failure_category",
    "summary",
    "role",
    "agency_id",
    "merchant_store_url",
    "demo_store_url",
)


def state_path(session_id: str) -> Path:
    return STATE_DIR / f"{session_id}.json"


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
    parser.add_argument("--agency", dest="agency_id")
    parser.add_argument("--store", dest="merchant_store_url")
    parser.add_argument("--demo-store", dest="demo_store_url")
    args = parser.parse_args()

    if not args.session_id:
        print("no session id (pass --session-id or set CLAUDE_CODE_SESSION_ID)", file=sys.stderr)
        return 1

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = state_path(args.session_id)
        current = json.loads(path.read_text()) if path.exists() else {}
        for field in FIELDS:
            value = getattr(args, field)
            if value is not None:
                current[field] = value
        path.write_text(json.dumps(current))
    except Exception as exc:
        print(f"telemetry state write failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
