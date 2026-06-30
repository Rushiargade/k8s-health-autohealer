"""Prometheus metrics exporter — the data source for the Grafana dashboard and for
Prometheus/Alertmanager rules. Served on /metrics (default :9090).
"""
from __future__ import annotations
from prometheus_client import Gauge, Counter, start_http_server

NODES_TOTAL = Gauge("autohealer_nodes_total", "Total nodes observed")
NODES_READY = Gauge("autohealer_nodes_ready", "Nodes in Ready state")
PODS_TOTAL = Gauge("autohealer_pods_total", "Total pods observed")
PODS_UNHEALTHY = Gauge("autohealer_pods_unhealthy", "Unhealthy pods, by issue", ["issue"])
NODE_CPU = Gauge("autohealer_node_cpu_percent", "Node CPU utilisation %", ["node"])
NODE_MEM = Gauge("autohealer_node_memory_percent", "Node memory utilisation %", ["node"])
HEAL_ACTIONS = Counter("autohealer_actions_total", "Healing actions taken", ["action", "result"])


def serve(port):
    start_http_server(port)


def record_action(action, result):
    HEAL_ACTIONS.labels(action=action, result=result).inc()
