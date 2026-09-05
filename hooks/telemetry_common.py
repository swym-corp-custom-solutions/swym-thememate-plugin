#!/usr/bin/env python3
"""Shared state-dir, identity, and send helpers for the ThemeMate telemetry hooks.

Used by both telemetry-hook.py (session_start/session_end) and telemetry_state.py
(session_heartbeat), so the kill switch, transport-safety gate, and file permissions
behave identically no matter which script is sending.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

ENDPOINT = os.environ.get("THEMEMATE_TELEMETRY_ENDPOINT", "http://127.0.0.1:8092/v1/telemetry/events")
PLAINTEXT_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
STATE_DIR = Path.home() / ".claude" / ".thememate-telemetry"
SESSIONS_DIR = STATE_DIR / "sessions"
INSTALL_ID_FILE = STATE_DIR / "install_id"
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
SKILL_MANIFEST = PLUGIN_ROOT / "skills" / "thememate" / "SKILL.md"

SEND_SNIPPET = (
    "import sys,urllib.request\n"
    "req=urllib.request.Request(sys.argv[1], data=sys.argv[2].encode(), "
    "headers={'Content-Type':'application/json'}, method='POST')\n"
    "try:\n"
    "    urllib.request.urlopen(req, timeout=3)\n"
    "except Exception:\n"
    "    pass\n"
)


def telemetry_disabled() -> bool:
    return bool(os.environ.get("THEMEMATE_TELEMETRY_DISABLED"))


def endpoint_is_safe(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and parsed.hostname in PLAINTEXT_ALLOWED_HOSTS


def ensure_state_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except Exception:
        pass


def atomic_write(path: Path, data: str, mode: int) -> None:
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(data)
    tmp.chmod(mode)
    os.replace(tmp, path)


def install_id() -> str:
    ensure_state_dir(STATE_DIR)
    if not INSTALL_ID_FILE.exists():
        INSTALL_ID_FILE.write_text(str(uuid.uuid4()))
        INSTALL_ID_FILE.chmod(0o600)
    return INSTALL_ID_FILE.read_text().strip()


def skill_version() -> str:
    try:
        frontmatter = SKILL_MANIFEST.read_text().split("---")[1]
        match = re.search(r"^\s*version:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"


def send_event(payload: dict) -> None:
    """Fire-and-forget POST, honoring the kill switch and the transport-safety gate."""
    if telemetry_disabled() or not endpoint_is_safe(ENDPOINT):
        return
    try:
        subprocess.Popen(
            [sys.executable, "-c", SEND_SNIPPET, ENDPOINT, json.dumps(payload)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass
