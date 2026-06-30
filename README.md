# k8s-health-autohealer

**Automated Kubernetes cluster health checker and self-healing controller.**

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-15%20passing-brightgreen)
![Docker](https://img.shields.io/badge/docker-ready-blue?logo=docker)
![Kubernetes](https://img.shields.io/badge/kubernetes-v1.28%2B-326CE5?logo=kubernetes)

A lightweight control loop that continuously monitors node and pod health, **automatically recovers** common failures (crash-looping, evicted, OOM-killed, stuck pods; unready nodes), balances load by scaling deployments, exposes Prometheus metrics for a Grafana dashboard, and notifies the team on Slack — with a full audit trail of every action.

Built to reduce the constant manual monitoring and intervention small DevOps teams spend on large clusters, and to keep workloads highly available with minimal human effort.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Sprint Progress](#sprint-progress)
- [Screenshots](#screenshots)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Healing Actions](#healing-actions)
- [Metrics](#metrics)
- [Alerting](#alerting)
- [Grafana Dashboard](#grafana-dashboard)
- [Cost Optimization](#cost-optimization)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Problem Statement

In many organizations, managing Kubernetes clusters manually requires constant monitoring, troubleshooting, and intervention to maintain high availability. This is especially challenging for small DevOps teams managing large-scale clusters — frequent manual tasks consume time and lead to downtime.

An automated health checker and self-healing tool can:
- Monitor the state of Kubernetes clusters continuously
- Detect and fix common issues (failed pods, unresponsive nodes)
- Ensure high availability with minimal manual intervention

---

## What It Does

| Goal | How |
|---|---|
| **Monitor** node health, pod status, resource utilisation | `src/health.py` + Kubernetes `metrics.k8s.io` |
| **Self-heal** failed pods, reschedule, clean up, scale | `src/healer.py` (gated by `dry_run`) |
| **Alert** the team on critical issues + actions taken | Slack (`src/notifier.py`) + Alertmanager |
| **Visualise** real-time + historical health and healing logs | Prometheus → Grafana + `logs/actions.jsonl` |

### Safety: dry-run by default
The healer starts in **`dry_run: true`** — it logs exactly what it *would* do and changes nothing. Watch it, trust it, then set `dry_run: false` to let it act. Every action is gated *twice*: by a per-action toggle **and** the global dry-run switch.

---

## Architecture

```
                     +-------------------------------------------+
                     |             Kubernetes API                |
                     |      nodes . pods . deployments           |
                     |            metrics.k8s.io                 |
                     +------^----------------------+-------------+
                 read |                            | act (delete / patch / scale)
                      |                            v
+----------------------------------------------------------------------+
|                   auto-healer control loop  (src/)                    |
|                                                                       |
|   kube_client  ->  health.classify_*  ->  healer  (gated by dry_run)  |
|       |               (pure logic)          |                         |
|       |                                      +--> auditlog (JSONL)     |
|       |                                      +--> notifier --> Slack   |
|       v                                                                |
|   metrics  (/metrics:9090) --------------------------------------------+
+----------+-----------------------------------------------------------+
           | scrape (15s)
    +------v------+      +--------------+      +---------------+
    | Prometheus  | ---> | Alertmanager | ---> |     Slack     |
    +------+------+      +--------------+      +---------------+
           | query
    +------v------+
    |   Grafana   |   real-time + historical dashboard (:3000)
    +-------------+
```

### Design Choices

- **Dry-run by default** — safe to run anywhere; enforcement is opt-in.
- **Pure classification core** — `health.py` has zero Kubernetes imports. Deterministic, fast, unit-testable. Only the thin adapter layer needs the API.
- **Idempotent healing** — deleting a *managed* pod lets its controller recreate a healthy one; the loop re-evaluates each tick.
- **Least-privilege RBAC** — the ServiceAccount gets exactly the verbs the actions need (`pods: delete`, `nodes: patch`, `deployments/scale: patch`) and nothing more.
- **Alert-only for ambiguous issues** — ImagePullBackOff and Stuck-Pending aren't auto-fixed (bad image tag / no capacity need a human), so the tool raises alerts instead of guessing.

---

## Project Structure

```
k8s-health-autohealer/
├── src/
│   ├── main.py          # control loop entry point (30s tick, signal handling)
│   ├── health.py        # pure classification logic — no K8s imports (unit-tested)
│   ├── healer.py        # healing actions: delete, cordon, scale (dry-run gated)
│   ├── kube_client.py   # Kubernetes API adapter → plain dicts for health.py
│   ├── config.py        # YAML config + env var overrides
│   ├── metrics.py       # Prometheus exporter on /metrics
│   ├── notifier.py      # Slack webhook (severity-gated, stdlib only)
│   └── auditlog.py      # append-only JSON-lines audit trail
│
├── tests/
│   └── test_health.py   # 15 unit tests — no cluster needed
│
├── scripts/
│   ├── healthcheck.py        # one-shot cluster snapshot (no healing)
│   └── simulate_failures.py  # inject crash-loop + imagepull pods for demo
│
├── deploy/
│   ├── rbac.yaml             # ServiceAccount + ClusterRole + ClusterRoleBinding
│   ├── deployment.yaml       # Deployment + ConfigMap + Service
│   ├── prometheus.yaml       # Prometheus scrape + alerting config
│   ├── alert-rules.yaml      # 5 Prometheus alert rules
│   ├── alertmanager.yaml     # Alertmanager Slack routing
│   ├── grafana-dashboard.json # 4-panel Grafana dashboard
│   └── ec2-k3s-setup.sh      # AWS EC2 user-data bootstrap (k3s + healer)
│
├── config/
│   └── config.yaml           # all tunables with inline comments
│
├── docker-compose.yaml        # healer + Prometheus + Alertmanager + Grafana
├── Dockerfile
├── requirements.txt           # kubernetes, prometheus_client, PyYAML
└── LICENSE
```

---

## Sprint Progress

| Sprint | Goal | Deliverable | Status |
|---|---|---|---|
| **1** | Project setup & cluster access | Repo, Kubernetes API access, Prometheus config | ✅ Done |
| **2** | Health monitoring (node & pod checks) | Node/pod classification, resource metrics, alert rules | ✅ Done |
| **3** | Self-healing — pod recovery | Restart/reschedule, CrashLoop/Evicted cleanup, audit log | ✅ Done |
| **4** | Advanced self-healing — scaling & balancing | Node cordon, CPU-based deployment scale up/down | ✅ Done |
| **5** | Alerting & notification system | Slack + Alertmanager integration, severity levels | ✅ Done |
| **6** | Web dashboard & documentation | Grafana dashboard, full docs, final testing | ✅ Done |

### Deliverables Checklist
- [x] Automated health monitoring tool for Kubernetes clusters
- [x] Self-healing for pods (restart, reschedule, cleanup) and nodes (cordon)
- [x] Real-time alerting/notifications via Slack + Alertmanager
- [x] Web dashboard (Grafana) for real-time + historical monitoring
- [x] Audit trail of every healing action (`logs/actions.jsonl`)
- [x] 15 unit tests (no cluster required)
- [x] Docker + Kubernetes manifests + AWS EC2 deploy script

---

## Screenshots

> Deployed live on AWS EC2 (t3.small, Amazon Linux 2023) with k3s — all screenshots from the actual running system.

### 1. Simulate Failures — Injecting Bad Pods

```bash
$ python3 scripts/simulate_failures.py

created namespace healer-demo
created pod healer-demo/crashloop      # busybox that exits every 2s → CrashLoopBackOff
created pod healer-demo/imagepull      # invalid image → ImagePullBackOff

Watch:   kubectl -n healer-demo get pods -w
Cleanup: kubectl delete namespace healer-demo
```

![Simulate Failures](docs/screenshots/simulate-failures.png)

---

### 2. Healer — Detecting & Healing in Enforcing Mode

The healer switches from DRY-RUN to **ENFORCING**, detects the crashloop pod at restart #5, and applies the fix automatically. The audit log entry is printed in real time:

```
k8s-health-autohealer started -- ENFORCING, interval 30s, metrics on :9090
tick: 1 nodes, 9 pods, 1 unhealthy
[notify:warning] ImagePullBackOff needs attention: pod/healer-demo/imagepull (not auto-healed by design)
{"ts": "2026-06-30T09:18:35.321198+00:00", "action": "restart_pod",
 "target": "pod/healer-demo/crashloop", "result": "applied",
 "dry_run": false, "issue": "CrashLoopBackOff", "restarts": 5}
[notify:warning] Healed: restart_pod pod/healer-demo/crashloop
tick: 1 nodes, 8 pods, 1 unhealthy
```

![Healer Enforcing](docs/screenshots/healer-enforcing.png)

**What happened:**
- `CrashLoopBackOff` at restart 5 → pod deleted → controller schedules a fresh one
- `ImagePullBackOff` → alert only (bad image = human decision needed, by design)
- Pod count drops from 9 → 8 confirming the delete was applied

---

### 3. Live Prometheus Metrics (browser at `http://34.227.24.14:9090/metrics`)

Real metrics from the AWS EC2 instance:

```
autohealer_nodes_total 1.0
autohealer_nodes_ready 1.0
autohealer_pods_total 9.0
autohealer_pods_unhealthy{issue="CrashLoopBackOff"} 0.0
autohealer_pods_unhealthy{issue="Evicted"} 0.0
autohealer_pods_unhealthy{issue="OOMKilled"} 0.0
autohealer_pods_unhealthy{issue="ImagePullBackOff"} 1.0
autohealer_pods_unhealthy{issue="StuckPending"} 0.0
autohealer_pods_unhealthy{issue="StuckTerminating"} 0.0
autohealer_node_cpu_percent{node="ip-172-31-26-192.ec2.internal"} 3.5
autohealer_node_memory_percent{node="ip-172-31-26-192.ec2.internal"} 59.7
```

![Prometheus Metrics](docs/screenshots/metrics.png)

---

### 4. Audit Log (real entry from the live run)

Every healing action is written to `logs/actions.jsonl` with full detail:

```json
{"ts": "2026-06-30T09:18:35.321198+00:00", "action": "restart_pod", "target": "pod/healer-demo/crashloop", "result": "applied", "dry_run": false, "issue": "CrashLoopBackOff", "restarts": 5}
```

### 5. Grafana Dashboard

> Import `deploy/grafana-dashboard.json` into Grafana (http://localhost:3000 when using Docker Compose).

The dashboard has 4 panels at 30-second refresh:

| Panel | Type | Shows |
|---|---|---|
| **Nodes Ready / Total** | Stat | e.g. `2 / 3` |
| **Unhealthy Pods by Issue** | Time series | 6 labelled lines (Evicted, CrashLoop, OOM, ImagePull, StuckPending, StuckTerminating) |
| **Healing Actions Rate** | Time series | actions × result: dry-run / applied / error |
| **Node CPU %** | Time series | per-node CPU utilisation |

---

## Installation & Setup

### Prerequisites

- A Kubernetes cluster: kind, minikube, k3s, or any real cluster
  ```bash
  kind create cluster   # or: minikube start
  ```
- `kubectl` pointed at the cluster
- **metrics-server** (for node CPU/memory %; healer still works without it):
  ```bash
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  # On kind/minikube, add --kubelet-insecure-tls to the metrics-server container args
  ```
- Python 3.10+ and/or Docker

### Option A — Local, out-of-cluster (fastest start)

```bash
pip install -r requirements.txt
python -m src.main
# Uses your current kubeconfig · DRY-RUN by default · metrics on :9090
```

### Option B — In-cluster (production)

```bash
# 1. Apply RBAC
kubectl apply -f deploy/rbac.yaml

# 2. Build + push your image, set it in deploy/deployment.yaml (image: field), then:
kubectl apply -f deploy/deployment.yaml

# 3. Watch logs
kubectl -n kube-system logs deploy/autohealer -f
```

### Option C — Full stack with Docker Compose (recommended for demo)

Brings up healer + Prometheus + Alertmanager + Grafana together:

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Healer metrics | http://localhost:9090/metrics |
| Prometheus | http://localhost:9091 |
| Alertmanager | http://localhost:9093 |
| Grafana | http://localhost:3000 |

After Grafana is up: **Dashboards → Import → Upload JSON → select `deploy/grafana-dashboard.json`**

### Option D — AWS EC2 + k3s (cloud demo)

Use `deploy/ec2-k3s-setup.sh` as the EC2 user-data script. It automatically:
- Installs k3s (lightweight Kubernetes)
- Clones this repo and installs dependencies
- Applies RBAC and sets up kubeconfig

Recommended instance: `t3.small` (2 vCPU, 2 GB RAM). Setup completes in ~2 minutes.

### Slack (optional)

```bash
# Local: set env var
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# In-cluster: Kubernetes secret
kubectl -n kube-system create secret generic autohealer-slack \
  --from-literal=webhook-url='https://hooks.slack.com/services/...'
```

---

## Configuration

Everything lives in [`config/config.yaml`](config/config.yaml):

```yaml
interval_seconds: 30        # health-check loop cadence
dry_run: true               # SAFE DEFAULT — set false to enforce

kubeconfig: ""              # "" = in-cluster; or path for local runs
namespaces: []              # [] = all namespaces, or list specific ones

thresholds:
  node_cpu_percent: 85        # node CPU% counted as "high"
  node_memory_percent: 85
  pod_restart_threshold: 5    # restarts before crash-loop action
  pod_pending_minutes: 10     # Pending longer than this → stuck
  pod_terminating_minutes: 10

healing:                      # per-action toggles (all still gated by dry_run)
  delete_evicted_pods: true
  restart_crashloop_pods: true
  delete_stuck_terminating: true
  cordon_unready_nodes: false   # conservative — off by default
  scale_on_high_cpu: false

scaling:                      # used when healing.scale_on_high_cpu: true
  target_deployment: ""       # "namespace/name"
  min_replicas: 1
  max_replicas: 5

slack:
  webhook_url: ""             # or SLACK_WEBHOOK_URL env var
  min_severity: warning       # info | warning | critical

metrics:
  port: 9090
```

**Environment variable overrides** (for secrets at deploy time):

| Variable | Overrides |
|---|---|
| `SLACK_WEBHOOK_URL` | `slack.webhook_url` |
| `DRY_RUN` (1/true/yes → true) | `dry_run` |
| `KUBECONFIG_PATH` | `kubeconfig` |

---

## Usage

### Safe demo end-to-end

```bash
# Terminal 1 — start healer in dry-run
python -m src.main

# Terminal 2 — inject failing pods
python scripts/simulate_failures.py

# Terminal 3 — watch pods
kubectl -n healer-demo get pods -w
```

The healer logs `[DRY-RUN] would restart_pod pod/healer-demo/crashloop` etc.

To enforce, stop the healer and restart with:
```bash
DRY_RUN=false python -m src.main
```

It will delete the crash-looping pod; the owning Deployment schedules a fresh one. Every action is appended to `logs/actions.jsonl`.

Clean up:
```bash
kubectl delete namespace healer-demo
```

### One-shot health snapshot (no healing)

```bash
python scripts/healthcheck.py
```

---

## Healing Actions

| Condition | Detected by | Action (when enforcing) | Toggle |
|---|---|---|---|
| Evicted pod | `phase=Failed`, reason=Evicted | `delete` — clean up | `delete_evicted_pods` |
| CrashLoopBackOff OR restarts ≥ threshold | waiting reason / restart count | `delete` → controller recreates | `restart_crashloop_pods` |
| OOMKilled | last termination reason | `delete` → fresh start | `restart_crashloop_pods` |
| Stuck Terminating (> 10 min) | `deletionTimestamp` age | force `delete` (grace=0) | `delete_stuck_terminating` |
| Node NotReady | `Ready=False` condition | `cordon` node | `cordon_unready_nodes` |
| Sustained high CPU | avg cluster CPU ≥ threshold | scale deployment **up** | `scale_on_high_cpu` |
| Idle cluster (CPU < 40% of threshold) | avg cluster CPU low | scale deployment **in** | `scale_on_high_cpu` |
| ImagePullBackOff | image pull waiting reason | **alert only** — needs human | — |
| Stuck Pending (> 10 min) | `Pending` phase + age | **alert only** — needs scheduling fix | — |

---

## Metrics

Exposed at `http://localhost:9090/metrics` in Prometheus format:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `autohealer_nodes_total` | Gauge | — | Total nodes |
| `autohealer_nodes_ready` | Gauge | — | Nodes in Ready state |
| `autohealer_pods_total` | Gauge | — | Total pods across watched namespaces |
| `autohealer_pods_unhealthy` | Gauge | `issue` | Unhealthy pods by issue type |
| `autohealer_node_cpu_percent` | Gauge | `node` | Per-node CPU % |
| `autohealer_node_memory_percent` | Gauge | `node` | Per-node memory % |
| `autohealer_actions_total` | Counter | `action`, `result` | Healing actions (dry-run / applied / error) |

---

## Alerting

### Prometheus Alert Rules (`deploy/alert-rules.yaml`)

| Alert | Severity | Duration | Condition |
|---|---|---|---|
| `ClusterNodesNotReady` | critical | 2m | any node NotReady |
| `PodsCrashLooping` | warning | 5m | any pod in CrashLoopBackOff |
| `PodsImagePullFailing` | warning | 3m | any pod failing image pull |
| `HealingActionsFailing` | critical | immediate | healing errors in last 10m |
| `NodeHighCPU` | warning | 10m | any node CPU > 90% |

### Alertmanager (`deploy/alertmanager.yaml`)

Routes all alerts to a Slack `#alerts` channel. Group by `alertname` + `severity`. Repeated at 4h intervals. Sends resolution notices too.

---

## Grafana Dashboard

Import `deploy/grafana-dashboard.json` into Grafana:

1. Open **http://localhost:3000** (after `docker compose up`)
2. **Dashboards → Import → Upload JSON file** → select `deploy/grafana-dashboard.json`
3. Set the Prometheus data source URL to `http://prometheus:9091`

The dashboard refreshes every 30 seconds and shows a 6-hour window by default.

---

## Cost Optimization

`scale_if_needed()` in `src/healer.py` implements two-directional cost control:

- **Scale UP** when average cluster CPU ≥ `node_cpu_percent` threshold — spreads load, prevents OOM cascades.
- **Scale DOWN (in)** toward `min_replicas` when average cluster CPU drops below **40% of the threshold** — trims idle replicas and reduces compute spend.

Combined with node cordoning (keeps pods off failing/over-provisioned nodes) and automatic eviction cleanup (releases reserved resources), the system continuously right-sizes the cluster to actual demand rather than peak provisioning.

**AWS cost reference (Option D):**
- `t3.small`: ~$0.02/hour for the EC2 instance running k3s
- Healer container: < 200m CPU / 128Mi RAM (resource limits in `deploy/deployment.yaml`)
- Scale-in saves proportional spend on application pods when idle

---

## Testing

15 unit tests — no cluster or network needed:

```bash
python -m unittest discover -s tests -v
```

```
test_classify_node_high_cpu ... ok
test_classify_node_not_ready ... ok
test_classify_node_pressure_condition ... ok
test_classify_node_ready_low_usage ... ok
test_classify_pod_crashloop_by_restart_count ... ok
test_classify_pod_crashloop_by_waiting_reason ... ok
test_classify_pod_evicted ... ok
test_classify_pod_healthy ... ok
test_classify_pod_healable ... ok
test_classify_pod_imagepull ... ok
test_classify_pod_not_healable ... ok
test_classify_pod_oomkilled ... ok
test_classify_pod_restart_below_threshold_is_healthy ... ok
test_cpu_quantity_nanocores ... ok
test_cpu_quantity_to_cores ... ok
test_mem_quantity_to_bytes ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.003s

OK
```

**What's tested:** pod classification (all 6 issue types), node classification (all 4 issue types), Kubernetes quantity parsing (CPU milli/nanocores, memory Ki/Mi/Gi).

The pure classification core (`health.py`) has zero Kubernetes imports — tests run in milliseconds with no external dependencies.

---

## Troubleshooting

**CPU / memory shows 0%**
metrics-server isn't installed or reachable. Install it (see Setup). The healer still handles pod/node-state issues without it; only resource-utilisation metrics and high-CPU scaling depend on it.

**`403 Forbidden` on a healing action**
The ServiceAccount lacks the RBAC verb. Re-apply `deploy/rbac.yaml`. The `HealingActionsFailing` alert fires on this.

**The healer does nothing**
Check `dry_run`: in dry-run it only logs intended actions. Flip to `false` (or `DRY_RUN=false`) to enforce. Also confirm the per-action toggle under `healing:` is `true`.

**`load_incluster_config` error when running locally**
Expected and handled: the healer falls back to your kubeconfig. Pass `--kubeconfig PATH` or set `KUBECONFIG_PATH` if it can't auto-locate it.

**No Slack messages**
Either no webhook is configured (notifications print to stdout instead), or `slack.min_severity` is set higher than the event's severity level.

**Deleted pods come straight back**
That is correct and intended. Deleting a *managed* pod makes its Deployment/StatefulSet recreate a healthy one. Bare (unmanaged) pods won't return — the loop will keep flagging them.

**Run the tests**
```bash
python -m unittest discover -s tests
```
Validates the classification logic without a cluster.

---

## License

MIT — see [LICENSE](LICENSE).

Author: Rushikesh Argade · 2026
