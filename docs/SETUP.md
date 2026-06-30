# Setup

## Prerequisites
- A Kubernetes cluster — kind, minikube, k3s, or any real cluster.
  Local quick start: `kind create cluster` or `minikube start`.
- `kubectl` pointed at that cluster.
- **metrics-server** (recommended — gives node CPU/memory %):
  ```bash
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  ```
  On kind/minikube, add `--kubelet-insecure-tls` to the metrics-server container args.
- Python 3.10+ (for local runs) and/or Docker.

## Option A — run locally (out of cluster)
```bash
pip install -r requirements.txt
python -m src.main          # uses your current kubeconfig; DRY-RUN by default
```
Metrics: <http://localhost:9090/metrics>

## Option B — run inside the cluster
```bash
kubectl apply -f deploy/rbac.yaml
# build + push the image, set it in deploy/deployment.yaml (image:), then:
kubectl apply -f deploy/deployment.yaml
kubectl -n kube-system logs deploy/autohealer -f
```

## Option C — full demo stack (Docker Compose)
Brings up the healer + Prometheus + Alertmanager + Grafana together:
```bash
docker compose up --build
```
- Healer metrics: <http://localhost:9090/metrics>
- Prometheus: <http://localhost:9091>
- Alertmanager: <http://localhost:9093>
- Grafana: <http://localhost:3000> — import `deploy/grafana-dashboard.json`

## Slack (optional)
Create an incoming webhook, then either:
- set `SLACK_WEBHOOK_URL` in the environment, or
- in-cluster: `kubectl -n kube-system create secret generic autohealer-slack --from-literal=webhook-url='https://hooks.slack.com/...'`
