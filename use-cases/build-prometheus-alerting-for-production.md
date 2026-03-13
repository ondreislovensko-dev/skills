---
title: Build Prometheus Alerting for Production Services
slug: build-prometheus-alerting-for-production
description: >-
  Set up Prometheus monitoring with Grafana dashboards and alert rules for
  production services — track API latency, error rates, resource usage,
  and get actionable alerts via Slack and PagerDuty.
skills:
  - grafana
  - prometheus-alertmanager
  - loki
  - docker-compose
  - nginx
category: infrastructure
tags:
  - monitoring
  - alerting
  - prometheus
  - grafana
  - observability
---

# Build Prometheus Alerting for Production Services

Chen runs a SaaS with 5 microservices and finds out about outages from angry customer emails. He needs monitoring that catches problems before users do — high error rates, slow API responses, disk filling up, memory leaks. He wants dashboards for daily health checks and alerts that wake him up only when it matters, not for every minor blip.

## Step 1: Instrument Your API

```typescript
// src/metrics.ts
import { collectDefaultMetrics, Counter, Histogram, Gauge, Registry } from "prom-client";

export const register = new Registry();
collectDefaultMetrics({ register });

export const httpRequestDuration = new Histogram({
  name: "http_request_duration_seconds",
  help: "Duration of HTTP requests in seconds",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

export const httpRequestTotal = new Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests",
  labelNames: ["method", "route", "status_code"],
  registers: [register],
});

export const activeConnections = new Gauge({
  name: "active_connections",
  help: "Number of active connections",
  registers: [register],
});

export const dbQueryDuration = new Histogram({
  name: "db_query_duration_seconds",
  help: "Duration of database queries",
  labelNames: ["operation", "table"],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
  registers: [register],
});
```

```typescript
// src/middleware/metrics.ts — Express middleware
import { httpRequestDuration, httpRequestTotal, activeConnections } from "../metrics";

export function metricsMiddleware(req: Request, res: Response, next: NextFunction) {
  activeConnections.inc();
  const end = httpRequestDuration.startTimer();

  res.on("finish", () => {
    const route = req.route?.path || req.path;
    const labels = { method: req.method, route, status_code: res.statusCode };
    end(labels);
    httpRequestTotal.inc(labels);
    activeConnections.dec();
  });

  next();
}
```

## Step 2: Prometheus Configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: "api-service"
    static_configs:
      - targets: ["api:3000"]
    metrics_path: /metrics

  - job_name: "nginx"
    static_configs:
      - targets: ["nginx-exporter:9113"]

  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]

  - job_name: "postgres"
    static_configs:
      - targets: ["postgres-exporter:9187"]
```

## Step 3: Alert Rules

```yaml
# prometheus/alerts/api.yml
groups:
  - name: api-alerts
    rules:
      # High error rate — fires if >5% of requests are 5xx for 5 minutes
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status_code=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate: {{ $value | humanizePercentage }}"
          description: "More than 5% of API requests are returning 5xx errors."

      # Slow API — P95 latency > 2 seconds
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
          > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency is {{ $value | humanizeDuration }}"

      # Database slow queries
      - alert: SlowDatabaseQueries
        expr: |
          histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (le))
          > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Database P95 query time is {{ $value | humanizeDuration }}"

  - name: infrastructure-alerts
    rules:
      # Disk space < 15%
      - alert: DiskSpaceLow
        expr: |
          (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) < 0.15
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Disk space below 15% on {{ $labels.instance }}"

      # Memory usage > 90%
      - alert: HighMemoryUsage
        expr: |
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage above 90% on {{ $labels.instance }}"

      # CPU sustained > 80%
      - alert: HighCPUUsage
        expr: |
          100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[10m])) * 100) > 80
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "CPU usage above 80% for 15 minutes on {{ $labels.instance }}"
```

## Step 4: Alertmanager with Smart Routing

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: "slack-default"
  group_by: ["alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    # Critical alerts → PagerDuty + Slack
    - match:
        severity: critical
      receiver: "pagerduty-critical"
      repeat_interval: 1h
    # Warnings → Slack only
    - match:
        severity: warning
      receiver: "slack-warnings"
      repeat_interval: 8h

receivers:
  - name: "slack-default"
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#alerts"
        title: '{{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
        send_resolved: true

  - name: "slack-warnings"
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#alerts-low"
        send_resolved: true

  - name: "pagerduty-critical"
    pagerduty_configs:
      - service_key: "${PAGERDUTY_SERVICE_KEY}"
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#alerts-critical"
        send_resolved: true

# Silence weekend non-critical alerts
inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["alertname"]
```

## Step 5: Docker Compose Stack

```yaml
# docker-compose.monitoring.yml
version: "3.8"
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus-data:/prometheus
    command: --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.retention.time=30d
    ports: ["9090:9090"]

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./alertmanager:/etc/alertmanager
    ports: ["9093:9093"]

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    ports: ["3001:3000"]

  node-exporter:
    image: prom/node-exporter:latest
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro

  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]

volumes:
  prometheus-data:
  grafana-data:
```

## Summary

Chen now gets Slack alerts when error rates spike above 5% or P95 latency exceeds 2 seconds — and only after the condition persists for 5 minutes (no alert fatigue from transient blips). Critical issues page him via PagerDuty, warnings go to a low-priority Slack channel. The Grafana dashboard shows real-time API latency percentiles, error rates by endpoint, database query times, and infrastructure metrics. He catches problems in minutes instead of hearing about them hours later from customers.
