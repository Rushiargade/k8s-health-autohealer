# Usage

## Safety first: dry-run
The healer ships with `dry_run: true`. It logs exactly what it WOULD do and changes nothing.
Run it, watch the logs and metrics, confirm the decisions look right, **then** set
`dry_run: false` (or `DRY_RUN=false`) to let it act.

## Demo the self-healing end to end
1. Start the healer (dry-run): `python -m src.main`
2. In another terminal, create failing pods:
   ```bash
   python scripts/simulate_failures.py
   ```
3. Watch the healer detect them — it logs e.g.
   `[DRY-RUN] would restart_pod pod/healer-demo/crashloop`
4. Set `dry_run: false` and restart the healer — now it deletes the crash-looping pod and the
   owning controller schedules a fresh one. Every action is appended to `logs/actions.jsonl`.
5. Clean up: `kubectl delete namespace healer-demo`

## One-shot health snapshot (no healing)
```bash
python scripts/healthcheck.py
```

## What it heals (when enforcing)
| Condition | Action | Toggle |
|---|---|---|
| Evicted pod | delete (clean up) | `delete_evicted_pods` |
| CrashLoopBackOff / restarts ≥ threshold | delete → controller recreates | `restart_crashloop_pods` |
| OOMKilled | delete → fresh start | `restart_crashloop_pods` |
| Stuck Terminating | force delete (grace 0) | `delete_stuck_terminating` |
| Node NotReady | cordon | `cordon_unready_nodes` |
| Sustained high CPU | scale target deployment up; scale in when idle | `scale_on_high_cpu` |
| ImagePullBackOff, Stuck Pending | **alert only** (needs a human) | — |

## Tuning
All thresholds and per-action switches live in `config/config.yaml` (or the ConfigMap in
`deploy/deployment.yaml`). Each is commented inline.
