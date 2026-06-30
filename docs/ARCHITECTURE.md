# Architecture

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
   |   metrics  (/metrics) ------------------------------------------------+
   +-----------+----------------------------------------------------------+
               | scrape
        +------v------+      +--------------+      +---------------+
        | Prometheus  | ---> | Alertmanager | ---> |     Slack     |
        +------+------+      +--------------+      +---------------+
               | query
        +------v------+
        |   Grafana   |   real-time + historical dashboard
        +-------------+
```

## Components

- **kube_client** — talks to the Kubernetes API and adapts live API objects into the plain
  dicts the health checks expect. The `kubernetes` import is lazy, so the pure modules and the
  unit tests load without the client library or a cluster.
- **health** — **pure** classification of node and pod conditions. Deterministic, fast, and
  unit-tested (`tests/test_health.py`). The single source of truth for "what's wrong".
- **healer** — decides and executes healing actions. Each action is gated by a per-action
  config toggle **and** the global `dry_run` flag, and is recorded to the audit log, the
  Prometheus counter, and Slack.
- **metrics** — Prometheus exporter on `/metrics`; the data source for Grafana and the alert rules.
- **notifier** — severity-gated Slack webhook, standard library only.
- **auditlog** — append-only JSON-lines record of every decision and action, for traceability.
- **main** — the monitor → heal → alert → export loop (default every 30s).

## Design choices

- **Dry-run by default.** Safe to run anywhere; enforcement is opt-in. The loop logs every
  intended action so you can validate behaviour before trusting it.
- **Pure classification core.** All the decision logic operates on plain dicts with no cluster
  dependency, which makes it fast, deterministic, and unit-testable. Only the thin adapter layer
  needs the API.
- **Idempotent healing.** Deleting a *managed* pod lets its controller recreate a healthy one;
  the loop re-evaluates each tick, so a still-broken target is handled again next pass — no
  state machine to get stuck.
- **Least-privilege RBAC.** The ServiceAccount gets exactly the verbs the actions need
  (`pods: delete`, `nodes: patch`, `deployments/scale: patch`) and nothing more.
- **Alert-only for ambiguous issues.** ImagePullBackOff and stuck-Pending aren't auto-fixed —
  they usually need a human (bad image tag) or a scheduling decision (no capacity), so the tool
  raises them instead of guessing.
