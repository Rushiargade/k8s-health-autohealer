#!/usr/bin/env python3
"""Create deliberately-failing pods so you can watch the auto-healer react.

Spins up a CrashLoopBackOff pod and an ImagePullBackOff pod in a throwaway namespace.

Usage:    python scripts/simulate_failures.py [--namespace healer-demo] [--kubeconfig PATH]
Clean up: kubectl delete namespace healer-demo
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import kube_client                  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", default="healer-demo")
    ap.add_argument("--kubeconfig", default="")
    args = ap.parse_args()

    from kubernetes import client
    core, _apps, _custom = kube_client.build_clients(args.kubeconfig)
    ns = args.namespace

    try:
        core.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=ns)))
        print(f"created namespace {ns}")
    except Exception as e:
        print(f"namespace {ns}: {e}")

    pods = {
        "crashloop": client.V1Pod(
            metadata=client.V1ObjectMeta(name="crashloop", labels={"demo": "autohealer"}),
            spec=client.V1PodSpec(restart_policy="Always", containers=[
                client.V1Container(name="boom", image="busybox",
                                   command=["sh", "-c", "echo starting; sleep 2; exit 1"])])),
        "imagepull": client.V1Pod(
            metadata=client.V1ObjectMeta(name="imagepull", labels={"demo": "autohealer"}),
            spec=client.V1PodSpec(containers=[
                client.V1Container(name="nope", image="registry.invalid/does-not-exist:latest")])),
    }
    for name, pod in pods.items():
        try:
            core.create_namespaced_pod(ns, pod)
            print(f"created pod {ns}/{name}")
        except Exception as e:
            print(f"pod {name}: {e}")

    print(f"\nWatch:   kubectl -n {ns} get pods -w")
    print(f"Cleanup: kubectl delete namespace {ns}")


if __name__ == "__main__":
    main()
