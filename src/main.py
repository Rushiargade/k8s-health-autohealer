"""Entry point — the monitor -> heal -> alert -> export loop.

Run as a module:  python -m src.main
"""
from __future__ import annotations
import signal
import time

from .config import load_config
from .auditlog import AuditLog
from .notifier import Notifier
from . import metrics, healer, health, kube_client

_running = True


def _stop(*_):
    global _running
    _running = False


def run_once(core, apps, custom, config, audit, notifier):
    nodes = kube_client.list_nodes(core, custom)
    pods = kube_client.list_pods(core, config.get("namespaces") or None)

    # --- export metrics ---
    metrics.NODES_TOTAL.set(len(nodes))
    metrics.NODES_READY.set(sum(1 for n in nodes if n["ready"]))
    metrics.PODS_TOTAL.set(len(pods))
    counts = {}
    for p in pods:
        issue = health.classify_pod(p, config["thresholds"])
        if issue:
            counts[issue] = counts.get(issue, 0) + 1
    for issue in (health.CRASHLOOP, health.EVICTED, health.OOMKILLED,
                  health.IMAGEPULL, health.STUCK_PENDING, health.STUCK_TERMINATING):
        metrics.PODS_UNHEALTHY.labels(issue=issue).set(counts.get(issue, 0))
    for n in nodes:
        metrics.NODE_CPU.labels(node=n["name"]).set(n.get("cpu_percent", 0))
        metrics.NODE_MEM.labels(node=n["name"]).set(n.get("memory_percent", 0))

    # --- heal ---
    healer.heal_pods(pods, core, config, audit, notifier)
    healer.heal_nodes(nodes, core, config, audit, notifier)
    healer.scale_if_needed(nodes, apps, config, audit, notifier)
    return len(nodes), len(pods), sum(counts.values())


def main():
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    config = load_config()
    audit = AuditLog()
    notifier = Notifier(config["slack"]["webhook_url"], config["slack"]["min_severity"])
    metrics.serve(config["metrics"]["port"])
    core, apps, custom = kube_client.build_clients(config.get("kubeconfig", ""))

    mode = "DRY-RUN" if config.get("dry_run", True) else "ENFORCING"
    print(f"k8s-health-autohealer started -- {mode}, interval {config['interval_seconds']}s, "
          f"metrics on :{config['metrics']['port']}", flush=True)
    notifier.send("info", f"Auto-healer started ({mode})")

    while _running:
        try:
            n, p, bad = run_once(core, apps, custom, config, audit, notifier)
            print(f"tick: {n} nodes, {p} pods, {bad} unhealthy", flush=True)
        except Exception as e:
            print(f"[loop:error] {e}", flush=True)
        for _ in range(config["interval_seconds"]):
            if not _running:
                break
            time.sleep(1)
    print("shutting down", flush=True)


if __name__ == "__main__":
    main()
