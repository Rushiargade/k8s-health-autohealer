# k8s-health-autohealer

**Automated Kubernetes cluster health checker and self-healing controller.**

A lightweight control loop that continuously monitors node and pod health, **automatically
recovers** common failures (crash-looping, evicted, OOM-killed, stuck pods; unready nodes),
balances load by scaling deployments, exposes Prometheus metrics for a Grafana dashboard, and
notifies the team on Slack — with a full audit trail of every action.

Built to reduce the constant manual monitoring and intervention small DevOps teams spend on
large clusters, and to keep workloads highly available with minimal human effort.

---

## What it does

| Goal | How |
|---|---|
| **Monitor** node health, pod status, resource utilisation | `src/health.py` + `metrics.k8s.io` |
| **Self-heal** failed pods, reschedule, clean up, scale | `src/healer.py` (gated by `dry_run`) |
| **Alert** the team on critical issues + actions taken | Slack (`src/notifier.py`) + Alertmanager |
| **Visualise** real-time + historical health and healing logs | Prometheus → Grafana + `logs/actions.jsonl` |

## Safety: dry-run by default
The healer starts in **`dry_run: true`** — it logs exactly what it *would* do and changes
nothing. Watch it, trust it, then set `dry_run: false` to let it act. Every action is gated
*twice*: by a per-action toggle **and** the global dry-run switch.

## Architecture

```
        Kubernetes API  ──read──▶  health.classify_*  (pure, unit-tested)
              ▲                            │
       act    │                            ▼
   (delete/   │                    healer  ──▶ auditlog (JSON lines)
    patch/    │                       │     ──▶ notifier  ──▶ Slack
    scale)    └────────────────────── │
                                       ▼
                              metrics  /metrics  ──scrape──▶ Prometheus
                                                                │
                                              Alertmanager ◀────┤
                                                  │             ▼
                                                Slack        Grafana
```
Full diagram + component notes in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

```bash
# 1. install + run locally against your current kubeconfig (DRY-RUN)
pip install -r requirements.txt
python -m src.main

# 2. in another shell, create failing pods and watch it react
python scripts/simulate_failures.py
kubectl -n healer-demo get pods -w

# 3. metrics
curl localhost:9090/metrics | grep autohealer_
```

Or bring up the **full stack** (healer + Prometheus + Alertmanager + Grafana):
```bash
docker compose up --build
# Grafana http://localhost:3000  ·  Prometheus http://localhost:9091
```

In-cluster deploy:
```bash
kubectl apply -f deploy/rbac.yaml
kubectl apply -f deploy/deployment.yaml      # set image: first
```

See [docs/SETUP.md](docs/SETUP.md) and [docs/USAGE.md](docs/USAGE.md).

## Healing actions

| Condition | Action when enforcing |
|---|---|
| Evicted pod | delete (clean up) |
| CrashLoopBackOff / restarts ≥ threshold | delete → controller recreates a fresh pod |
| OOMKilled | delete → fresh start |
| Stuck Terminating | force delete (grace 0) |
| Node NotReady *(opt-in)* | cordon |
| Sustained high CPU *(opt-in)* | scale the target deployment up; scale **in** when idle |
| ImagePullBackOff, Stuck Pending | **alert only** — needs a human / scheduling fix |

## Configuration
Everything is in [`config/config.yaml`](config/config.yaml) — intervals, thresholds, per-action
toggles, scaling target, Slack severity. Secrets (`SLACK_WEBHOOK_URL`) and the `DRY_RUN` switch
can be set via environment variables so nothing sensitive lives in the repo.

## Metrics
Exposed on `/metrics`: `autohealer_nodes_total`, `autohealer_nodes_ready`,
`autohealer_pods_total`, `autohealer_pods_unhealthy{issue}`, `autohealer_node_cpu_percent{node}`,
`autohealer_actions_total{action,result}`. Prometheus alert rules in
[`deploy/alert-rules.yaml`](deploy/alert-rules.yaml); Grafana dashboard in
[`deploy/grafana-dashboard.json`](deploy/grafana-dashboard.json).

## Project structure
```
src/        health (pure checks) · healer (actions) · kube_client · metrics · notifier · auditlog · main
deploy/     rbac · deployment · prometheus · alert-rules · alertmanager · grafana-dashboard
scripts/    healthcheck (snapshot) · simulate_failures (demo)
tests/      unit tests for the classification logic
docs/       architecture · setup · usage · troubleshooting · sprint mapping
```

## Testing
```bash
python -m unittest discover -s tests       # 15 tests, no cluster needed
```

## Cost optimisation
`scale_if_needed()` scales workloads **in** toward `min_replicas` when nodes sit below 40% of
the CPU threshold, and cordoning keeps pods off failing nodes — together trimming idle capacity
and wasted spend. See [docs/SPRINTS.md](docs/SPRINTS.md).

## License
MIT — see [LICENSE](LICENSE).
