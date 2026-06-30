"""Slack notifications for critical issues and healing actions.

Uses an incoming-webhook URL and the standard library only (no extra deps). Severity
gated, so info-level chatter stays out of the channel. With no webhook configured it
degrades to a logged no-op, so the tool still runs cleanly in a demo without Slack.
"""
from __future__ import annotations
import json
import urllib.request

_SEV_RANK = {"info": 0, "warning": 1, "critical": 2}
_EMOJI = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}


class Notifier:
    def __init__(self, webhook_url="", min_severity="warning"):
        self.webhook_url = webhook_url
        self.min_rank = _SEV_RANK.get(min_severity, 1)

    def send(self, severity, text):
        if _SEV_RANK.get(severity, 0) < self.min_rank:
            return False
        if not self.webhook_url:
            print(f"[notify:{severity}] {text}", flush=True)
            return False
        body = json.dumps({"text": f"{_EMOJI.get(severity, '')} *[{severity.upper()}]* {text}"}).encode()
        req = urllib.request.Request(self.webhook_url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return 200 <= r.status < 300
        except Exception as e:  # never let a notification failure crash the loop
            print(f"[notify:error] {e}", flush=True)
            return False
