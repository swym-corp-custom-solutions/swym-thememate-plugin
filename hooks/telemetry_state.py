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
import re
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / ".thememate-telemetry" / "sessions"
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")

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
    return STATE_DIR / f"{session_id}.json"


def atomic_write(path: Path, data: str, mode: int) -> None:
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(data)
    tmp.chmod(mode)
    os.replace(tmp, path)


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
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_DIR.chmod(0o700)
        STATE_DIR.parent.chmod(0o700)
        path = state_path(args.session_id)
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
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
