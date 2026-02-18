---
name: prometheus-monitoring
description: >-
  Set up and configure Prometheus, Grafana, and Alertmanager for infrastructure and application
  monitoring. Use when someone asks to "set up monitoring", "create Grafana dashboards",
  "configure alerts", "monitor services", "track SLOs", or "build observability stack".
  Covers metrics collection, PromQL queries, recording rules, alert rules, and dashboard design.
license: Apache-2.0
compatibility: "Prometheus 2.x, Grafana 10+, Alertmanager 0.27+, Node Exporter, cAdvisor"
metadata:
  author: terminal-skills
  category: devops
  tags:
    - monitoring
    - prometheus
    - grafana
    - alertmanager
    - observability
    - metrics
    - slo
    - devops
---

# Prometheus Monitoring

You are an infrastructure monitoring expert specializing in Prometheus, Grafana, and Alertmanager. You design metrics pipelines, write PromQL queries, configure alerting rules, and build dashboards that give teams real visibility into system health.

## Core Stack

### Prometheus — Metrics Collection & Storage

**prometheus.yml — Main Configuration**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

rule_files:
  - "rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]
    relabel_configs:
      - source_labels: [__address__]
        regex: "(.+):.*"
        target_label: instance
        replacement: "$1"

  - job_name: "app"
    metrics_path: /metrics
    static_configs:
      - targets: ["app:8080"]

  # Service discovery for Kubernetes
  - job_name: "kubernetes-pods"
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # Docker service discovery
  - job_name: "docker"
    dockerswarm_sd_configs:
      - host: unix:///var/run/docker.sock
        role: tasks
```

**Docker Compose — Full Stack**
```yaml
version: "3.8"

services:
  prometheus:
    image: prom/prometheus:v2.51.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules:/etc/prometheus/rules
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
      - "--storage.tsdb.retention.size=10GB"
      - "--web.enable-lifecycle"
      - "--web.enable-admin-api"
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.4.0
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=https://grafana.example.com
    ports:
      - "3000:3000"
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.27.0
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.7.0
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - "--path.procfs=/host/proc"
      - "--path.sysfs=/host/sys"
      - "--path.rootfs=/rootfs"
      - "--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)"
    ports:
      - "9100:9100"
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports:
      - "8080:8080"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

### PromQL — Query Language

**Basic Queries**
```promql
# Current CPU usage percentage per instance
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage percentage
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

# Disk usage percentage
(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100

# Network traffic rate (bytes/sec)
rate(node_network_receive_bytes_total{device="eth0"}[5m])
```

**Application Metrics**
```promql
# Request rate (requests per second)
rate(http_requests_total[5m])

# Error rate percentage
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Apdex score (satisfied < 0.5s, tolerating < 2s)
(
  sum(rate(http_request_duration_seconds_bucket{le="0.5"}[5m])) +
  sum(rate(http_request_duration_seconds_bucket{le="2.0"}[5m]))
) / 2 / sum(rate(http_request_duration_seconds_count[5m]))
```

**SLO Queries**
```promql
# Availability SLO — percentage of successful requests over 30 days
1 - (sum(increase(http_requests_total{status=~"5.."}[30d])) / sum(increase(http_requests_total[30d])))

# Error budget remaining
1 - (
  sum(increase(http_requests_total{status=~"5.."}[30d])) /
  sum(increase(http_requests_total[30d]))
) / (1 - 0.999)

# Burn rate (how fast error budget is consumed)
sum(rate(http_requests_total{status=~"5.."}[1h])) / sum(rate(http_requests_total[1h])) / 0.001
```

### Recording Rules

```yaml
# rules/recording.yml
groups:
  - name: app_metrics
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))

      - record: job:http_errors:rate5m
        expr: sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))

      - record: job:http_error_ratio:rate5m
        expr: job:http_errors:rate5m / job:http_requests:rate5m

      - record: job:http_latency_p99:5m
        expr: histogram_quantile(0.99, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))

  - name: node_metrics
    rules:
      - record: instance:cpu_usage:rate5m
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

      - record: instance:memory_usage:ratio
        expr: 1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes

      - record: instance:disk_usage:ratio
        expr: 1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}
```

### Alert Rules

```yaml
# rules/alerts.yml
groups:
  - name: infrastructure
    rules:
      - alert: HighCpuUsage
        expr: instance:cpu_usage:rate5m > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is {{ printf \"%.1f\" $value }}% for 10+ minutes."

      - alert: HighMemoryUsage
        expr: instance:memory_usage:ratio > 0.90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is {{ printf \"%.1f\" (mul $value 100) }}%."

      - alert: DiskSpaceLow
        expr: instance:disk_usage:ratio > 0.85
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space low on {{ $labels.instance }}"
          description: "Disk usage is {{ printf \"%.1f\" (mul $value 100) }}%. Will fill in {{ printf \"%.0f\" (node_filesystem_avail_bytes{mountpoint=\"/\"} / (rate(node_filesystem_avail_bytes{mountpoint=\"/\"}[1h]) * -1) / 3600) }} hours."

      - alert: InstanceDown
        expr: up == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Instance {{ $labels.instance }} is down"
          description: "{{ $labels.job }}/{{ $labels.instance }} has been down for 3+ minutes."

  - name: application
    rules:
      - alert: HighErrorRate
        expr: job:http_error_ratio:rate5m > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate for {{ $labels.job }}"
          description: "Error rate is {{ printf \"%.2f\" (mul $value 100) }}% (threshold: 5%)."

      - alert: HighLatency
        expr: job:http_latency_p99:5m > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High p99 latency for {{ $labels.job }}"
          description: "p99 latency is {{ printf \"%.2f\" $value }}s (threshold: 2s)."

      - alert: ErrorBudgetBurnRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[1h])) /
          sum(rate(http_requests_total[1h])) / 0.001 > 14.4
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error budget burning fast"
          description: "At current burn rate ({{ printf \"%.1f\" $value }}x), error budget exhausts in < 2 hours."
```

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_from: "alerts@example.com"
  smtp_smarthost: "smtp.example.com:587"
  smtp_auth_username: "alerts@example.com"
  smtp_auth_password: "${SMTP_PASSWORD}"
  slack_api_url: "${SLACK_WEBHOOK_URL}"

route:
  group_by: ["alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: "default"
  routes:
    - match:
        severity: critical
      receiver: "pagerduty-critical"
      group_wait: 10s
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: "slack-warnings"

receivers:
  - name: "default"
    slack_configs:
      - channel: "#alerts"
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: "pagerduty-critical"
    pagerduty_configs:
      - service_key: "${PAGERDUTY_SERVICE_KEY}"
        severity: critical

  - name: "slack-warnings"
    slack_configs:
      - channel: "#alerts-warning"
        title: '⚠️ {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["alertname", "instance"]
```

### Grafana Dashboard Provisioning

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

```yaml
# grafana/provisioning/dashboards/default.yml
apiVersion: 1
providers:
  - name: "default"
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

### Application Instrumentation

**Node.js (prom-client)**
```javascript
const client = require('prom-client');

// Default metrics (CPU, memory, event loop)
client.collectDefaultMetrics({ prefix: 'app_' });

// Custom counters
const httpRequests = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'path', 'status'],
});

// Histograms for latency
const httpDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds',
  labelNames: ['method', 'path'],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
});

// Middleware
app.use((req, res, next) => {
  const end = httpDuration.startTimer({ method: req.method, path: req.route?.path || req.path });
  res.on('finish', () => {
    httpRequests.inc({ method: req.method, path: req.route?.path || req.path, status: res.statusCode });
    end();
  });
  next();
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});
```

**Python (prometheus_client)**
```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

REQUEST_COUNT = Counter('http_requests_total', 'Total requests', ['method', 'path', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'Request duration',
                              ['method', 'path'],
                              buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10])

# Flask middleware
@app.before_request
def before_request():
    request._start_time = time.time()

@app.after_request
def after_request(response):
    duration = time.time() - request._start_time
    REQUEST_COUNT.labels(request.method, request.path, response.status_code).inc()
    REQUEST_DURATION.labels(request.method, request.path).observe(duration)
    return response

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
```

## Workflow

1. **Assess** — Identify what needs monitoring (infrastructure, app, business metrics)
2. **Instrument** — Add metrics endpoints to applications
3. **Configure** — Set up Prometheus scrape targets and service discovery
4. **Record** — Create recording rules for expensive or frequently-used queries
5. **Alert** — Define alert rules with meaningful thresholds and for-durations
6. **Visualize** — Build Grafana dashboards for different audiences (ops, dev, business)
7. **Iterate** — Review alert noise, adjust thresholds, add new metrics as needed

## Best Practices

- Use recording rules for any query used in dashboards or alerts — saves compute on every evaluation
- Set `for` duration on alerts to avoid flapping (minimum 5m for warnings, 2-3m for critical)
- Use inhibit rules to suppress warning alerts when critical is already firing
- Label metrics consistently: `job`, `instance`, `namespace`, `service`
- Keep cardinality under control — never use unbounded label values (user IDs, request IDs)
- Use histograms over summaries for latency — they're aggregatable across instances
- Dashboard hierarchy: overview → service → instance (drill-down pattern)
- Store Grafana dashboards as JSON in version control, provision via config
