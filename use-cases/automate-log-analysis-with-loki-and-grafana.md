---
title: Automate Log Analysis with Loki and Grafana
slug: automate-log-analysis-with-loki-and-grafana
description: >-
  Set up centralized log aggregation with Grafana Loki — collect logs from
  multiple services, build searchable dashboards, create alerts on error
  patterns, and correlate logs with metrics for faster debugging.
skills:
  - loki
  - grafana
  - docker-compose
  - prometheus-alertmanager
category: infrastructure
tags:
  - logging
  - observability
  - loki
  - grafana
  - debugging
---

# Automate Log Analysis with Loki and Grafana

Sven's team debugs production issues by SSH-ing into servers and grep-ing through log files. With 4 services across 3 servers, finding the relevant logs for one user's request takes 20 minutes. He needs centralized logging: all logs in one place, searchable by service/level/user/request-id, with alerts when error patterns spike. Loki is the Prometheus of logs — lightweight, label-based, and integrates natively with Grafana.

## Step 1: Deploy Loki Stack

```yaml
# docker-compose.logging.yml
version: "3.8"
services:
  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
    volumes:
      - ./loki/config.yml:/etc/loki/config.yml
      - loki-data:/loki
    command: -config.file=/etc/loki/config.yml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./promtail/config.yml:/etc/promtail/config.yml
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}

volumes:
  loki-data:
  grafana-data:
```

```yaml
# loki/config.yml
auth_enabled: false
server:
  http_listen_port: 3100

common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /loki

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  filesystem:
    directory: /loki/chunks

limits_config:
  retention_period: 30d
  max_query_series: 5000

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
```

## Step 2: Structured Logging in Your App

```typescript
// src/lib/logger.ts
import pino from "pino";

export const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  formatters: {
    level: (label) => ({ level: label }),
  },
  base: {
    service: process.env.SERVICE_NAME || "api",
    env: process.env.NODE_ENV || "development",
  },
});

// Request-scoped logger with correlation ID
export function createRequestLogger(requestId: string, userId?: string) {
  return logger.child({ requestId, userId });
}
```

```typescript
// src/middleware/logging.ts
import { createRequestLogger } from "../lib/logger";
import { randomUUID } from "crypto";

export function loggingMiddleware(req: Request, res: Response, next: NextFunction) {
  const requestId = req.headers["x-request-id"] as string || randomUUID();
  const log = createRequestLogger(requestId, req.user?.id);

  req.log = log;
  res.setHeader("x-request-id", requestId);

  const start = Date.now();

  res.on("finish", () => {
    const duration = Date.now() - start;
    const logData = {
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      duration,
      userAgent: req.headers["user-agent"],
      ip: req.ip,
    };

    if (res.statusCode >= 500) {
      log.error(logData, "Request failed");
    } else if (res.statusCode >= 400) {
      log.warn(logData, "Client error");
    } else {
      log.info(logData, "Request completed");
    }
  });

  next();
}
```

## Step 3: Promtail Configuration

```yaml
# promtail/config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker container logs
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: container
      - source_labels: ["__meta_docker_container_label_com_docker_compose_service"]
        target_label: service
    pipeline_stages:
      # Parse JSON logs
      - json:
          expressions:
            level: level
            msg: msg
            requestId: requestId
            userId: userId
            service: service
            duration: duration
            statusCode: statusCode
      - labels:
          level:
          service:
      - timestamp:
          source: time
          format: RFC3339Nano
```

## Step 4: Useful LogQL Queries for Grafana

```logql
# All errors from the API service in the last hour
{service="api"} | json | level="error"

# Slow requests (>1 second)
{service="api"} | json | duration > 1000

# Errors for a specific user
{service="api"} | json | userId="user_abc123" | level=~"error|warn"

# Trace a request across services by request ID
{} | json | requestId="req_xyz789"

# Top 10 error messages
sum by (msg) (count_over_time({service="api"} | json | level="error" [1h]))

# Error rate over time (for dashboard graph)
sum(rate({service="api"} | json | level="error" [5m]))

# 95th percentile request duration
quantile_over_time(0.95, {service="api"} | json | unwrap duration [5m]) by (service)
```

## Step 5: Alert on Log Patterns

```yaml
# loki/alert-rules.yml
groups:
  - name: log-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({service="api"} | json | level="error" [5m])) > 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in API logs"
          description: "More than 1 error per second for 5 minutes"

      - alert: AuthenticationFailures
        expr: |
          sum(rate({service="api"} |= "authentication failed" [10m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Spike in authentication failures — possible brute force"

      - alert: DatabaseConnectionErrors
        expr: |
          count_over_time({service="api"} |= "ECONNREFUSED" or |= "connection timeout" [5m]) > 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection errors detected"
```

## Summary

Sven's team now debugs issues in minutes instead of 20. Every service ships structured JSON logs to Loki via Promtail. In Grafana, they search by service, level, user ID, or request ID — and trace a single request across all 4 services using the correlation ID. Dashboard panels show error rates over time, and alerts fire when error patterns spike or suspicious authentication failures appear. Log storage costs a fraction of Elasticsearch because Loki only indexes labels, not full text. The entire stack runs on a single $20/month VPS alongside their existing Grafana and Prometheus setup.
