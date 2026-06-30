# Troubleshooting

**CPU / memory shows 0%** — metrics-server isn't installed or reachable. Install it (see
SETUP.md). The healer still handles pod/node-state issues without it; only the utilisation
metrics and the high-CPU scaling depend on it.

**`403 Forbidden` on a healing action** — the ServiceAccount lacks the RBAC for that verb.
Re-apply `deploy/rbac.yaml`. The `HealingActionsFailing` alert fires on this.

**The healer does nothing** — check `dry_run`: in dry-run it only logs intended actions. Flip
it to `false` to enforce. Also confirm the relevant per-action toggle under `healing:` is `true`.

**`load_incluster_config` error when running locally** — expected, and handled: it falls back
to your kubeconfig. Pass `--kubeconfig PATH` or set `KUBECONFIG_PATH` if it can't auto-locate it.

**No Slack messages** — either no webhook is configured, or `slack.min_severity` is higher than
the event's severity. With no webhook the notifications print to stdout instead.

**Deleted pods come straight back** — that's correct and intended: deleting a *managed* pod
makes its Deployment/StatefulSet recreate a healthy one. Bare (unmanaged) pods won't return —
the loop will keep flagging them so you notice.

**Run the tests** — `python -m unittest discover -s tests` validates the classification logic
without a cluster.
