#!/usr/bin/env python3
"""One-shot cluster health snapshot — prints node + pod issues, takes NO action.

Usage:  python scripts/healthcheck.py [--kubeconfig PATH]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import kube_client, health          # noqa: E402
from src.config import load_config           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kubeconfig", default="")
    args = ap.parse_args()

    cfg = load_config()
    th = cfg["thresholds"]
    core, _apps, custom = kube_client.build_clients(args.kubeconfig or cfg.get("kubeconfig", ""))

    nodes = kube_client.list_nodes(core, custom)
    print(f"\nNODES ({len(nodes)})")
    for n in nodes:
        issues = health.classify_node(n, th)
        flag = "OK" if not issues else ", ".join(issues)
        print(f"  {n['name']:30} ready={str(n['ready']):5} "
              f"cpu={n.get('cpu_percent', 0):5}% mem={n.get('memory_percent', 0):5}%  {flag}")

    pods = kube_client.list_pods(core, cfg.get("namespaces") or None)
    bad = [(p, health.classify_pod(p, th)) for p in pods]
    bad = [(p, i) for p, i in bad if i]
    print(f"\nPODS: {len(pods)} total, {len(bad)} unhealthy")
    for p, issue in bad:
        print(f"  {p['namespace']}/{p['name']:40} {issue}  (restarts={p.get('restart_count', 0)})")
    print()


if __name__ == "__main__":
    main()
