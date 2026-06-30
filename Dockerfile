FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

# Run unprivileged — the healer's only authority is its Kubernetes RBAC, not root-in-container.
RUN useradd --create-home --uid 10001 healer
USER healer

EXPOSE 9090
ENTRYPOINT ["python", "-m", "src.main"]
