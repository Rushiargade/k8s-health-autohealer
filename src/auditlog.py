"""Structured audit log — every healing decision and action, as JSON lines.

Each record goes to stdout (so `kubectl logs` shows it) and is appended to a file so
the dashboard / evaluator can replay exactly what the healer did and why. This is the
traceability the project requires for self-healing actions.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone


class AuditLog:
    def __init__(self, path="logs/actions.jsonl"):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)

    def record(self, action, target, result, dry_run, **detail):
        """result is one of: 'applied' | 'dry-run' | 'error'."""
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target": target,
            "result": result,
            "dry_run": dry_run,
            **detail,
        }
        line = json.dumps(rec)
        print(line, flush=True)
        try:
            with open(self.path, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass  # stdout is the source of truth; the file is best-effort
        return rec
