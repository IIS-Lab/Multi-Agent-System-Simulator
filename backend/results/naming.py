"""Run IDs and result filenames.

Filename format: [{label}--]{username}_{YYYY-MM-DDTHH-MM-SS}_{run_id}.json  (timestamp in UTC)
Examples:        young_voices_ja--alice_2026-10-05T08-09-12_run_a83f2c.json
                 alice_2026-10-05T08-09-12_run_a83f2c.json   (no run name)

The label is the experiment's "Run name". Only letters, digits, '-' and '_'
are kept, so a name written only in other scripts (e.g. Japanese) is dropped
from the filename (it is still stored inside the JSON). The run_id keeps every
filename unique.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

RUN_ID_PATTERN = r"run_[0-9a-f]{6,}"
TIMESTAMP_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}"
LABEL_PATTERN = r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*"
RESULT_ID_RE = re.compile(
    rf"^(?:(?P<label>{LABEL_PATTERN})--)?(?P<username>[A-Za-z0-9_-]+)_(?P<timestamp>{TIMESTAMP_PATTERN})_(?P<run_id>{RUN_ID_PATTERN})$"
)


def new_run_id() -> str:
    return f"run_{secrets.token_hex(3)}"


def sanitize_username(username: str) -> str:
    """Make a username safe for filenames: letters, digits, '-' and '_' only."""
    safe = re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9_-]+", "-", username.strip())).strip("-_")
    return safe[:40].strip("-_") or "user"


def sanitize_label(label: str) -> str:
    """Make a run name safe for filenames; '' when nothing usable is left."""
    safe = re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9_-]+", "-", (label or "").strip())).strip("-_")
    return safe[:60].strip("-_")


def build_result_id(username: str, created_at: datetime, run_id: str, label: str = "") -> str:
    stamp = created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    prefix = sanitize_label(label)
    return f"{prefix + '--' if prefix else ''}{sanitize_username(username)}_{stamp}_{run_id}"


def result_filename(result_id: str) -> str:
    return f"{result_id}.json"


def parse_result_id(result_id: str) -> dict[str, str] | None:
    """Return label/username/timestamp/run_id parsed from a result id, or None if invalid."""
    match = RESULT_ID_RE.match(result_id)
    if not match:
        return None
    stamp = datetime.strptime(match["timestamp"], "%Y-%m-%dT%H-%M-%S").replace(tzinfo=timezone.utc)
    return {
        "label": match["label"] or "",
        "username": match["username"],
        "timestamp": stamp.isoformat().replace("+00:00", "Z"),
        "run_id": match["run_id"],
    }


def is_valid_result_id(result_id: str) -> bool:
    return RESULT_ID_RE.match(result_id) is not None
