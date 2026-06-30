"""Configuration loading.

Reads config/config.yaml and overlays environment variables, so secrets (the Slack
webhook) and the safety switch (dry-run) can be injected at deploy time without baking
them into the image or the repo.
"""
from __future__ import annotations
import os
import yaml

DEFAULTS = {
    "interval_seconds": 30,
    "dry_run": True,            # SAFE DEFAULT — log healing actions but do NOT execute them
    "kubeconfig": "",           # "" = in-cluster; otherwise a path to a kubeconfig
    "namespaces": [],           # [] = all namespaces
    "thresholds": {
        "node_cpu_percent": 85,
        "node_memory_percent": 85,
        "pod_restart_threshold": 5,
        "pod_pending_minutes": 10,
        "pod_terminating_minutes": 10,
    },
    "healing": {
        "delete_evicted_pods": True,
        "restart_crashloop_pods": True,
        "delete_stuck_terminating": True,
        "cordon_unready_nodes": False,   # node-level actions off by default (conservative)
        "scale_on_high_cpu": False,
    },
    "scaling": {"target_deployment": "", "min_replicas": 1, "max_replicas": 5},
    "slack": {"webhook_url": "", "min_severity": "warning"},
    "metrics": {"port": 9090},
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path="config/config.yaml"):
    cfg = _deep_merge(DEFAULTS, {})
    if os.path.exists(path):
        with open(path) as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
    # Environment overrides for things that should never live in a file.
    if os.environ.get("SLACK_WEBHOOK_URL"):
        cfg["slack"]["webhook_url"] = os.environ["SLACK_WEBHOOK_URL"]
    if os.environ.get("DRY_RUN") is not None and os.environ.get("DRY_RUN") != "":
        cfg["dry_run"] = os.environ["DRY_RUN"].lower() in ("1", "true", "yes")
    if os.environ.get("KUBECONFIG_PATH"):
        cfg["kubeconfig"] = os.environ["KUBECONFIG_PATH"]
    return cfg
