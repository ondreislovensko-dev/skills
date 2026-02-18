---
description: Deploy a full Prometheus + Grafana + Alertmanager monitoring stack to gain real-time visibility into infrastructure and application health, replacing blind spots with actionable dashboards and alerts
skills: [prometheus-monitoring, load-balancer]
---

# Set Up a Production Monitoring Stack and Cut Incident Response Time

## The Problem

Ravi runs platform engineering at a 40-person fintech startup. They have 12 microservices running on Kubernetes, but monitoring is a mess — scattered CloudWatch metrics, a few hand-made Grafana panels nobody trusts, and an on-call rotation that relies on customers reporting outages before engineers notice them.

Last month, a payment processing service hit 98% memory for 45 minutes before crashing. Nobody knew until merchants started calling support. The incident cost 2.3 hours of downtime and an estimated $47,000 in failed transactions. Post-mortem revealed: no memory alerts existed, no dashboards showed service-level health, and the existing "monitoring" was just uptime pings.

The CEO wants observability that actually works — proactive alerts, real dashboards, SLO tracking — before next quarter when transaction volume doubles.

## The Solution

Combine **prometheus-monitoring** for metrics collection, alerting, and SLO tracking with **load-balancer** for exposing Grafana securely and routing health check traffic. The approach: instrument everything, set meaningful alert thresholds (not noisy ones), build dashboards for different audiences, and validate with a chaos test.

## Step-by-Step Walkthrough

### 1. Deploy the monitoring stack

Set up Prometheus, Grafana, Alertmanager, and Node Exporter with Docker Compose. Prometheus should scrape all 12 services every 15 seconds, retain 30 days of data with a 10GB cap. Alertmanager routes critical alerts to PagerDuty and warnings to Slack #alerts-warning. Include cAdvisor for container metrics.

Expected output: docker-compose.yml, prometheus.yml with all scrape targets, alertmanager.yml with routing rules. All services healthy and Prometheus showing 12/12 targets UP on the /targets page.

### 2. Add application instrumentation

Add Prometheus client libraries to the two most critical services: payment-processor (Node.js) and merchant-api (Python). Expose standard HTTP metrics: request count by method/path/status, request duration histogram with buckets at 10ms/50ms/100ms/250ms/500ms/1s/2s/5s, and active connections gauge. Add business metrics: payment_transactions_total (by status: success/failed/timeout), payment_amount_sum, and merchant_api_calls_total.

Expected output: /metrics endpoints on both services returning Prometheus-format metrics. payment-processor showing ~200 req/s, merchant-api ~80 req/s on the Prometheus graph.

### 3. Create recording rules for performance

Write recording rules for frequently-used queries: per-service request rate (5m window), error ratio, p50/p95/p99 latency, and CPU/memory usage per pod. These pre-compute expensive queries so dashboards load instantly.

Expected output: recording-rules.yml with ~15 rules. Prometheus evaluation showing 0 errors. Dashboard queries using recorded metrics instead of raw rate() calculations.

### 4. Configure alert rules with SLO-based thresholds

Define alerts based on actual SLOs, not arbitrary numbers. Payment service SLO: 99.9% success rate, p99 latency < 500ms. Merchant API SLO: 99.5% availability, p99 < 2s. Infrastructure: CPU > 85% for 10min (warning), > 95% for 5min (critical). Memory > 90% for 10min. Disk > 85% for 5min. Add error budget burn rate alerts — if burning 14.4x faster than sustainable, fire critical immediately.

Expected output: alerts.yml with infrastructure group (5 rules) and application group (6 rules). All rules loaded in Prometheus with status "OK". Alertmanager receiving test alert and routing to correct channel.

### 5. Build Grafana dashboards for three audiences

**Operations overview** — Single pane showing all 12 services: UP/DOWN status, request rate, error rate, p99 latency. Red/yellow/green color coding. Time range selector. This is the on-call engineer's first stop during incidents.

**Service deep-dive** — Template variable for service name. Shows request rate breakdown by endpoint, latency percentiles over time, error rate with status code breakdown, resource usage (CPU/memory/network), and active connections. Engineers use this to diagnose which endpoint is slow and why.

**Business metrics** — Payment success rate (hourly/daily), transaction volume, revenue processed, top merchants by volume. Leadership reviews this weekly.

Provision all dashboards as JSON in version control so they survive Grafana restarts.

Expected output: 3 dashboards provisioned automatically. Operations overview loading in < 2 seconds with all 12 services visible. Service deep-dive showing payment-processor metrics when selected from dropdown.

### 6. Set up Nginx reverse proxy for Grafana

Configure Nginx to proxy Grafana on grafana.internal.example.com with SSL termination, basic auth as a second layer, and rate limiting (30 req/s per IP). Include WebSocket support for live dashboard updates. Add /health endpoint for load balancer health checks.

Expected output: Nginx config with SSL, proxy_pass to Grafana, WebSocket upgrade headers. Grafana accessible via HTTPS with live-updating panels. Rate limiting verified with test burst.

### 7. Validate with a controlled chaos test

Simulate the exact failure that caused last month's incident: gradually increase memory consumption on payment-processor until it hits 90%. Verify the alert fires within 3 minutes, PagerDuty notification arrives, and the operations dashboard shows the service in red. Then restore and verify alert resolves.

Expected output: Alert "HighMemoryUsage" fires at 90% after 10 minutes (per for-duration). PagerDuty incident created within 30 seconds of alert firing. Operations dashboard shows payment-processor in red with memory graph spiking. After recovery: alert resolves, dashboard returns to green, PagerDuty incident auto-resolves after 5-minute resolve_timeout.

## Expected Outcome

- **Incident detection**: from customer-reported (45 min+) to automated alert (< 3 min)
- **Dashboard load time**: < 2s for operations overview (recording rules eliminate slow queries)
- **Alert noise**: < 5 alerts/week (SLO-based thresholds, not arbitrary percentages)
- **MTTR reduction**: 45 min → ~12 min (engineers see the problem immediately, not after debugging blind)
- **Coverage**: 12/12 services instrumented, infrastructure + application + business metrics
- **Error budget visibility**: leadership sees exactly how much reliability margin remains before SLO breach
