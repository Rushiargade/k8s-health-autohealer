"""Kubernetes API access + adapters that turn live API objects into the plain dicts
health.py classifies. The `kubernetes` import lives inside build_clients() so the pure
modules (and the unit tests) import without the client library installed.
"""
from __future__ import annotations


def build_clients(kubeconfig=""):
    """Return (CoreV1Api, AppsV1Api, CustomObjectsApi). In-cluster by default; falls
    back to the local kubeconfig for out-of-cluster runs."""
    from kubernetes import client, config as kconfig
    if kubeconfig:
        kconfig.load_kube_config(config_file=kubeconfig)
    else:
        try:
            kconfig.load_incluster_config()
        except Exception:
            kconfig.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api(), client.CustomObjectsApi()


def _node_metrics(custom):
    """node name -> (cpu_cores_used, mem_bytes_used) from metrics.k8s.io, {} if absent."""
    out = {}
    try:
        data = custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
        for it in data.get("items", []):
            u = it.get("usage", {})
            out[it["metadata"]["name"]] = (cpu_to_cores(u.get("cpu", "0")), mem_to_bytes(u.get("memory", "0")))
    except Exception:
        pass  # metrics-server not installed → CPU/mem percentages just read 0
    return out


def list_nodes(core, custom):
    metrics = _node_metrics(custom)
    nodes = []
    for n in core.list_node().items:
        conds = {c.type: (c.status == "True") for c in (n.status.conditions or [])}
        cap = n.status.capacity or {}
        cpu_cap = cpu_to_cores(cap.get("cpu", "0")) or 1
        mem_cap = mem_to_bytes(cap.get("memory", "0")) or 1
        used_cpu, used_mem = metrics.get(n.metadata.name, (0, 0))
        nodes.append({
            "name": n.metadata.name,
            "ready": conds.get("Ready", False),
            "cpu_percent": round(used_cpu / cpu_cap * 100, 1) if cpu_cap else 0,
            "memory_percent": round(used_mem / mem_cap * 100, 1) if mem_cap else 0,
            "conditions": conds,
            "unschedulable": bool(n.spec.unschedulable),
        })
    return nodes


def list_pods(core, namespaces=None):
    raw = []
    if namespaces:
        for ns in namespaces:
            raw += core.list_namespaced_pod(ns).items
    else:
        raw = core.list_pod_for_all_namespaces().items
    pods = []
    for p in raw:
        st = p.status
        cs = st.container_statuses or []
        waiting = last_term = ""
        restarts = 0
        for c in cs:
            restarts += c.restart_count or 0
            if c.state and c.state.waiting and c.state.waiting.reason:
                waiting = c.state.waiting.reason
            if c.last_state and c.last_state.terminated and c.last_state.terminated.reason:
                last_term = c.last_state.terminated.reason
        pods.append({
            "namespace": p.metadata.namespace,
            "name": p.metadata.name,
            "node": p.spec.node_name,
            "phase": st.phase,
            "reason": st.reason or "",
            "ready": all(c.ready for c in cs) if cs else False,
            "restart_count": restarts,
            "waiting_reason": waiting,
            "last_terminated_reason": last_term,
            "deletion_timestamp": p.metadata.deletion_timestamp.isoformat() if p.metadata.deletion_timestamp else None,
            "start_time": st.start_time.isoformat() if st.start_time else None,
            "created_at": p.metadata.creation_timestamp.isoformat() if p.metadata.creation_timestamp else None,
        })
    return pods


# --- Kubernetes quantity-string parsing (pure, unit-tested) -----------------
def cpu_to_cores(q):
    q = str(q)
    if q.endswith("n"):
        return _f(q[:-1]) / 1e9
    if q.endswith("u"):
        return _f(q[:-1]) / 1e6
    if q.endswith("m"):
        return _f(q[:-1]) / 1000.0
    return _f(q)


def mem_to_bytes(q):
    q = str(q)
    units = {"Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3, "Ti": 1024 ** 4,
             "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
    for u, mult in units.items():
        if q.endswith(u):
            return _f(q[:-len(u)]) * mult
    return _f(q)


def _f(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
