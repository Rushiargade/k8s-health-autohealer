#!/bin/bash
# AWS EC2 user-data — stands up a single-node k3s (lightweight Kubernetes) cluster and
# prepares the auto-healer on boot. Chosen over EKS deliberately: k3s on one t3.small costs
# pennies vs EKS's ~$73/mo control plane — that's the project's cost-optimisation goal in action.
#
# How to use:
#   1. Push this repo to GitHub (public) and set REPO_URL below.
#   2. Launch an Ubuntu 22.04 t3.small, paste this whole file into "Advanced details > User data".
#   3. After ~2 min, SSH in and run:
#        cd k8s-health-autohealer
#        sudo -E KUBECONFIG=/etc/rancher/k3s/k3s.yaml python3 -m src.main
#   4. Screenshot the demo, then TERMINATE the instance.
set -e

REPO_URL="https://github.com/REPLACE_ME/k8s-health-autohealer.git"   # <-- set your repo URL

# Lightweight Kubernetes
curl -sfL https://get.k3s.io | sh -

# Tooling
apt-get update
apt-get install -y git python3-pip

# The project
cd /home/ubuntu
git clone "$REPO_URL"
cd k8s-health-autohealer
pip3 install -r requirements.txt
chown -R ubuntu:ubuntu /home/ubuntu/k8s-health-autohealer

# Healer RBAC + a kubeconfig the ubuntu user can read
KUBECONFIG=/etc/rancher/k3s/k3s.yaml k3s kubectl apply -f deploy/rbac.yaml
mkdir -p /home/ubuntu/.kube
cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/.kube/config
chown -R ubuntu:ubuntu /home/ubuntu/.kube

echo "k8s-health-autohealer setup complete" > /home/ubuntu/SETUP_DONE.txt
