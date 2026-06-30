"""Cluster health checks: classify node and pod conditions.

The classification functions here are PURE — they operate on plain dicts and import
nothing from the Kubernetes client, so they are deterministic and unit-tested without
a live cluster (see tests/test_health.py). kube_client.py adapts live API objects into
the dicts these functions expect.
"""
from __future__ import annotations
from datetime import datetime, timezone

# Pod issue categories the healer reasons about.
CRASHLOOP = "CrashLoopBackOff"
IMAGEPULL = "ImagePullBackOff"
EVICTED = "Evicted"
OOMKILLED = "OOMKilled"
STUCK_PENDING = "StuckPending"
STUCK_TERMINATING = "StuckTerminating"


def _age_minutes(ts, now=None):
    """Minutes since an ISO-8601 timestamp (or datetime). 0 when unknown."""
    if not ts:
        return 0.0
    now = now or datetime.now(timezone.utc)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (now - ts).total_seconds() / 60.0


def classify_pod(pod, thresholds, now=None):
    """Return an issue-category string for an unhealthy pod, or None if healthy.

    `pod` is a plain dict with any of:
      phase, reason, ready, restart_count, waiting_reason,
      last_terminated_reason, deletion_timestamp, start_time, created_at
    Order matters: the most actionable / most severe condition wins.
    """
    phase = pod.get("phase")
    reason = pod.get("reason") or ""
    waiting = pod.get("waiting_reason") or ""
    restarts = pod.get("restart_count", 0) or 0

    # Evicted — a dead pod left behind after node pressure; safe to clean up.
    if phase == "Failed" and reason == "Evicted":
        return EVICTED
    # Stuck Terminating — has a deletionTimestamp but lingered past the grace window.
    if pod.get("deletion_timestamp") and _age_minutes(pod["deletion_timestamp"], now) >= thresholds.get("pod_terminating_minutes", 10):
        return STUCK_TERMINATING
    # CrashLoopBackOff, or a restart count over the threshold = wedged in a restart loop.
    if waiting == CRASHLOOP or restarts >= thresholds.get("pod_restart_threshold", 5):
        return CRASHLOOP
    # Image pull failures — "applied" but the container never runs.
    if waiting in (IMAGEPULL, "ErrImagePull", "InvalidImageName", "ImageInspectError"):
        return IMAGEPULL
    # OOMKilled on the previous run.
    if pod.get("last_terminated_reason") == OOMKILLED:
        return OOMKILLED
    # Pending too long — unschedulable (no headroom / taints / missing PV).
    if phase == "Pending" and _age_minutes(pod.get("start_time") or pod.get("created_at"), now) >= thresholds.get("pod_pending_minutes", 10):
        return STUCK_PENDING
    return None


def classify_node(node, thresholds):
    """Return a list of issue strings for a node (empty list = healthy).

    `node` dict: name, ready (bool), cpu_percent, memory_percent, conditions {type: bool}.
    """
    issues = []
    if node.get("ready") is False:
        issues.append("NotReady")
    if (node.get("cpu_percent") or 0) >= thresholds.get("node_cpu_percent", 85):
        issues.append("HighCPU")
    if (node.get("memory_percent") or 0) >= thresholds.get("node_memory_percent", 85):
        issues.append("HighMemory")
    for cond in ("MemoryPressure", "DiskPressure", "PIDPressure"):
        if node.get("conditions", {}).get(cond) is True:
            issues.append(cond)
    return issues


# Issues the healer can safely auto-fix, and the action it takes for each.
HEALABLE = {
    EVICTED: "delete_pod",
    CRASHLOOP: "delete_pod",          # delete → the owning controller recreates a fresh pod
    OOMKILLED: "delete_pod",
    STUCK_TERMINATING: "force_delete_pod",
}
# Issues we ALERT on but never auto-fix — they need a human or a scheduling decision.
ALERT_ONLY = {IMAGEPULL, STUCK_PENDING}
