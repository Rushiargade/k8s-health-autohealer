"""Self-healing actions.

Every action is gated twice — by a per-action config toggle AND by the global
`dry_run` switch — and is recorded to the audit log, the Prometheus counter, and Slack.
In dry-run mode (the default) the healer logs exactly what it WOULD do and changes
nothing, which makes it safe to run anywhere and easy to demo.
"""
from __future__ import annotations
from . import health, metrics


def _do(api_call, *, action, target, audit, notifier, config, severity="warning", **detail):
    """Execute (or dry-run) one healing action with full audit + notify + metric."""
    if config.get("dry_run", True):
        audit.record(action, target, "dry-run", True, **detail)
        metrics.record_action(action, "dry-run")
        notifier.send("info", f"[DRY-RUN] would {action} {target}")
        return "dry-run"
    try:
        api_call()
        audit.record(action, target, "applied", False, **detail)
        metrics.record_action(action, "applied")
        notifier.send(severity, f"Healed: {action} {target}")
        return "applied"
    except Exception as e:
        audit.record(action, target, "error", False, error=str(e), **detail)
        metrics.record_action(action, "error")
        notifier.send("critical", f"Healing FAILED: {action} {target} -- {e}")
        return "error"


def heal_pods(pods, core, config, audit, notifier):
    th, hl = config["thresholds"], config["healing"]
    for pod in pods:
        issue = health.classify_pod(pod, th)
        if not issue:
            continue
        ns, name = pod["namespace"], pod["name"]
        target = f"pod/{ns}/{name}"
        if issue == health.EVICTED and hl.get("delete_evicted_pods"):
            _do(lambda n=name, s=ns: core.delete_namespaced_pod(n, s),
                action="delete_evicted_pod", target=target, audit=audit, notifier=notifier, config=config, issue=issue)
        elif issue in (health.CRASHLOOP, health.OOMKILLED) and hl.get("restart_crashloop_pods"):
            _do(lambda n=name, s=ns: core.delete_namespaced_pod(n, s),
                action="restart_pod", target=target, audit=audit, notifier=notifier, config=config, issue=issue, restarts=pod.get("restart_count"))
        elif issue == health.STUCK_TERMINATING and hl.get("delete_stuck_terminating"):
            def _force(n=name, s=ns):
                from kubernetes import client as kclient
                core.delete_namespaced_pod(n, s, body=kclient.V1DeleteOptions(grace_period_seconds=0))
            _do(_force, action="force_delete_pod", target=target, audit=audit, notifier=notifier, config=config, issue=issue)
        elif issue in health.ALERT_ONLY:
            notifier.send("warning", f"{issue} needs attention: {target} (not auto-healed by design)")


def heal_nodes(nodes, core, config, audit, notifier):
    th, hl = config["thresholds"], config["healing"]
    for node in nodes:
        issues = health.classify_node(node, th)
        if not issues:
            continue
        name = node["name"]
        if "NotReady" in issues and hl.get("cordon_unready_nodes") and not node.get("unschedulable"):
            _do(lambda n=name: core.patch_node(n, {"spec": {"unschedulable": True}}),
                action="cordon_node", target=f"node/{name}", audit=audit, notifier=notifier, config=config, severity="critical", issues=issues)
        else:
            sev = "critical" if "NotReady" in issues else "warning"
            notifier.send(sev, f"Node {name}: {', '.join(issues)}")


def scale_if_needed(nodes, apps, config, audit, notifier):
    """Sprint-4 cost/perf balancing: scale a target deployment up when average node CPU
    is high. Scaling DOWN toward min_replicas when idle is the cost-optimisation lever."""
    sc, hl = config.get("scaling", {}), config["healing"]
    target = sc.get("target_deployment")
    if not hl.get("scale_on_high_cpu") or not target or not nodes:
        return
    avg_cpu = sum(n.get("cpu_percent", 0) for n in nodes) / len(nodes)
    ns, _, dname = target.partition("/")
    if not dname:
        ns, dname = "default", ns
    high = avg_cpu >= config["thresholds"]["node_cpu_percent"]
    low = avg_cpu < config["thresholds"]["node_cpu_percent"] * 0.4

    def _scale():
        dep = apps.read_namespaced_deployment(dname, ns)
        cur = dep.spec.replicas or 1
        new = cur
        if high:
            new = min(cur + 1, sc.get("max_replicas", 5))
        elif low:
            new = max(cur - 1, sc.get("min_replicas", 1))   # scale in when idle -> saves cost
        if new != cur:
            apps.patch_namespaced_deployment_scale(dname, ns, {"spec": {"replicas": new}})
            return new
        return None

    if high or low:
        _do(_scale, action="scale_deployment", target=f"deploy/{ns}/{dname}", audit=audit, notifier=notifier, config=config, avg_cpu=round(avg_cpu, 1))
