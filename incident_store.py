
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

INCIDENT_FILE = Path(
    os.getenv("INCIDENT_FILE", "incidents/history.jsonl")
)

_write_lock = threading.Lock()


def record_incident(event_type, **details):
    """Append a timestamped incident event to persistent storage."""

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **details
    }

    with _write_lock:
        INCIDENT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with INCIDENT_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, default=str) + "\n")
            file.flush()
            os.fsync(file.fileno())

    return event


def read_incidents(limit=50):
    """Read incident history, optionally limiting the results."""

    if not INCIDENT_FILE.exists():
        return []

    events = []

    with INCIDENT_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit is None:
        return events

    if limit <= 0:
        return []

    return events[-limit:]


def count_incidents():
    """Count all persisted incident events."""

    return len(read_incidents(limit=None))
