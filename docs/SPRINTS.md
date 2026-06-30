# Sprint Deliverables Mapping

How each project sprint maps to what's in this repository.

| Sprint | Deliverable | Where |
|---|---|---|
| **1. Setup & cluster access** | Repo structure, Kubernetes API access, Prometheus config | `src/kube_client.py`, `deploy/rbac.yaml`, `deploy/prometheus.yaml`, `config/` |
| **2. Health monitoring (node & pod)** | Node/pod checks, resource metrics, thresholds, alerts | `src/health.py`, `src/metrics.py`, `deploy/alert-rules.yaml` |
| **3. Self-healing (pod recovery)** | Restart/reschedule, clean CrashLoop/Evicted, audit log | `src/healer.py` → `heal_pods()`, `src/auditlog.py` |
| **4. Advanced self-healing (scaling & balancing)** | Node cordon, deployment scale up/down on CPU | `src/healer.py` → `heal_nodes()`, `scale_if_needed()` |
| **5. Alerting & notifications** | Slack + Alertmanager, severity levels, docs | `src/notifier.py`, `deploy/alertmanager.yaml`, `deploy/alert-rules.yaml` |
| **6. Web dashboard & docs** | Grafana dashboard, metrics, full documentation | `deploy/grafana-dashboard.json`, `docs/`, `README.md` |

## Deliverables checklist
- [x] Automated health monitoring tool for Kubernetes clusters
- [x] Self-healing for pods (restart, reschedule, cleanup) and nodes (cordon)
- [x] Real-time alerting/notifications via Slack + Alertmanager
- [x] Web dashboard (Grafana) for real-time + historical monitoring
- [x] Audit trail of every healing action (`logs/actions.jsonl`)
- [x] Comprehensive documentation (architecture, setup, usage, troubleshooting)

## Evaluation-criteria coverage
- **Implementation (75%)** — a working monitor + self-healer + alerting + dashboard; the pure
  decision logic is unit-tested (`tests/`, 15 tests, no cluster required).
- **Documentation (15%)** — `README.md` plus `docs/` (architecture, setup, usage,
  troubleshooting, and this mapping).
- **Cost Optimization (10%)** — `scale_if_needed()` scales **in** toward `min_replicas` when
  nodes are idle (< 40% of the CPU threshold), and cordoning + rescheduling keep workloads off
  failing/over-provisioned nodes — reducing wasted capacity and spend. See `src/healer.py`.
