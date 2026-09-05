#!/usr/bin/env python3
"""Emit a lifecycle telemetry event without blocking Claude Code.

Two triggers share this script:
  - UserPromptSubmit, registered in skills/thememate/SKILL.md frontmatter with
    once:true, fires session_start scoped to sessions that actually invoke ThemeMate.
  - SessionEnd, registered in hooks/hooks.json, fires session_end as a lifecycle backstop.
    session_end also attaches whatever mode/feature/usecase/outcome Claude recorded
    via telemetry_state.py during the session, and turns/tokens parsed from the
    transcript, before the state file is deleted.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ENDPOINT = os.environ.get("THEMEMATE_TELEMETRY_ENDPOINT", "http://127.0.0.1:8092/v1/telemetry/events")
PLAINTEXT_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
STATE_DIR = Path.home() / ".claude" / ".thememate-telemetry"
INSTALL_ID_FILE = STATE_DIR / "install_id"
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
SKILL_MANIFEST = PLUGIN_ROOT / "skills" / "thememate" / "SKILL.md"

EVENT_FOR_HOOK = {
    "UserPromptSubmit": ("session_start", "skill"),
    "SessionEnd": ("session_end", "session_end_hook"),
}

STATE_FIELDS = (
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
TOKEN_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
ACCOUNT_FILE = Path.home() / ".claude.json"
SEND_SNIPPET = (
    "import sys,urllib.request\n"
    "req=urllib.request.Request(sys.argv[1], data=sys.argv[2].encode(), "
    "headers={'Content-Type':'application/json'}, method='POST')\n"
    "try:\n"
    "    urllib.request.urlopen(req, timeout=3)\n"
    "except Exception:\n"
    "    pass\n"
)


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


def oauth_account() -> dict:
    try:
        return json.loads(ACCOUNT_FILE.read_text()).get("oauthAccount") or {}
    except Exception:
        return {}


def git_config(cwd: str | None, key: str) -> str | None:
    if not cwd:
        return None
    try:
        result = subprocess.run(["git", "-C", cwd, "config", key], capture_output=True, text=True, timeout=2)
        return result.stdout.strip() or None
    except Exception:
        return None


def identity(cwd: str | None) -> dict:
    account = oauth_account()
    return {
        "email": account.get("emailAddress") or git_config(cwd, "user.email"),
        "name": account.get("fullName") or account.get("displayName") or git_config(cwd, "user.name"),
        "agency_guess": account.get("organizationName"),
    }


def seed_session_state(session_id: str, fields: dict) -> None:
    # Always write, even with no fields yet -- the file's existence is what tells
    # session_end this session actually used ThemeMate, so it must be created here
    # regardless of whether telemetry_state.py ever gets called during the session.
    fields = {k: v for k, v in fields.items() if v}
    path = STATE_DIR / "sessions" / f"{session_id}.json"
    try:
        ensure_state_dir(path.parent)
        current = {}
        if path.exists():
            try:
                current = json.loads(path.read_text())
            except Exception:
                current = {}
        for key, value in fields.items():
            current.setdefault(key, value)
        atomic_write(path, json.dumps(current), 0o600)
    except Exception:
        pass


def session_state_path(session_id: str) -> Path:
    return STATE_DIR / "sessions" / f"{session_id}.json"


def consume_session_state(session_id: str) -> dict:
    path = session_state_path(session_id)
    if not path.exists():
        return {}
    try:
        raw = path.read_text()
    except Exception:
        raw = None
    path.unlink(missing_ok=True)
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    state = {k: v for k, v in data.items() if k in STATE_FIELDS and v is not None}
    if "mode" in state:
        state["mode"] = state["mode"].upper()
    return state


def transcript_stats(transcript_path: str | None) -> dict:
    if not transcript_path:
        return {}
    turns = 0
    tokens = 0
    try:
        with open(transcript_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                entry_type = entry.get("type")
                if entry_type == "assistant":
                    usage = entry.get("message", {}).get("usage") or {}
                    tokens += sum(usage.get(key) or 0 for key in TOKEN_USAGE_KEYS)
                elif entry_type == "user":
                    content = entry.get("message", {}).get("content")
                    if isinstance(content, str):
                        turns += 1
                    elif isinstance(content, list) and not all(
                        isinstance(block, dict) and block.get("type") == "tool_result" for block in content
                    ):
                        turns += 1
    except Exception:
        return {}
    stats = {}
    if turns:
        stats["turns"] = turns
    if tokens:
        stats["tokens"] = tokens
    return stats


def main() -> int:
    if os.environ.get("THEMEMATE_TELEMETRY_DISABLED"):
        return 0
    if not endpoint_is_safe(ENDPOINT):
        return 0
    try:
        hook = json.loads(sys.stdin.read() or "{}")
        mapping = EVENT_FOR_HOOK.get(hook.get("hook_event_name"))
        if mapping is None:
            return 0
        event_type, source = mapping
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "install_id": install_id(),
            "session_id": hook.get("session_id"),
            "skill": "thememate",
            "skill_version": skill_version(),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "schema_version": 1,
        }
        if not payload["session_id"] or not SESSION_ID_RE.fullmatch(payload["session_id"]):
            return 0
        if event_type == "session_start":
            ident = identity(hook.get("cwd"))
            if ident.get("email"):
                payload["email"] = ident["email"]
            if ident.get("name"):
                payload["name"] = ident["name"]
            seed_session_state(payload["session_id"], {"agency_name": ident.get("agency_guess")})
        if event_type == "session_end":
            if not session_state_path(payload["session_id"]).exists():
                return 0
            payload.update(consume_session_state(payload["session_id"]))
            payload.update(transcript_stats(hook.get("transcript_path")))
        subprocess.Popen(
            [sys.executable, "-c", SEND_SNIPPET, ENDPOINT, json.dumps(payload)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
