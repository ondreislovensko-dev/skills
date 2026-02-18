---
name: load-balancer
description: >-
  Configure and optimize load balancers for web applications using Nginx, HAProxy, and cloud ALBs.
  Use when someone asks to "set up load balancing", "configure Nginx reverse proxy", "set up HAProxy",
  "configure SSL termination", "implement health checks", "handle WebSocket proxying",
  or "optimize traffic distribution". Covers L4/L7 balancing, SSL, rate limiting, and caching.
license: Apache-2.0
compatibility: "Nginx 1.25+, HAProxy 2.8+, AWS ALB/NLB, Cloudflare, Traefik"
metadata:
  author: terminal-skills
  category: devops
  tags:
    - load-balancer
    - nginx
    - haproxy
    - reverse-proxy
    - ssl
    - traffic
    - devops
    - networking
---

# Load Balancer

You are a traffic engineering expert specializing in load balancing, reverse proxying, and high-availability configurations. You design reliable, performant traffic routing using Nginx, HAProxy, and cloud load balancers.

## Nginx

### Reverse Proxy with Load Balancing
```nginx
# /etc/nginx/nginx.conf
user nginx;
worker_processes auto;
worker_rlimit_nofile 65535;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 4096;
    multi_accept on;
    use epoll;
}

http {
    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    types_hash_max_size 2048;
    server_tokens off;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" $request_time $upstream_response_time '
                    '$upstream_addr';
    access_log /var/log/nginx/access.log main buffer=16k flush=5s;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    limit_conn_zone $binary_remote_addr zone=conn:10m;

    # Upstream backends
    upstream app_servers {
        least_conn;
        keepalive 32;

        server app1:8080 weight=3 max_fails=3 fail_timeout=30s;
        server app2:8080 weight=3 max_fails=3 fail_timeout=30s;
        server app3:8080 weight=2 max_fails=3 fail_timeout=30s;
        server app4:8080 backup;
    }

    upstream websocket_servers {
        ip_hash;
        server ws1:8080;
        server ws2:8080;
    }

    upstream api_servers {
        zone api_zone 64k;
        least_conn;

        server api1:3000 weight=5;
        server api2:3000 weight=5;
        server api3:3000 weight=3;
    }

    # Caching
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=static_cache:10m
                     max_size=1g inactive=60m use_temp_path=off;

    # SSL session cache
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    include /etc/nginx/conf.d/*.conf;
}
```

### HTTPS Server with Proxy
```nginx
# /etc/nginx/conf.d/app.conf
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    # SSL
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files with caching
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        proxy_cache static_cache;
    }

    # API with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_conn conn 50;

        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        proxy_next_upstream error timeout http_502 http_503;
        proxy_next_upstream_tries 2;
    }

    # Auth endpoint — strict rate limit
    location /api/auth/login {
        limit_req zone=login burst=3 nodelay;

        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://websocket_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # App
    location / {
        proxy_pass http://app_servers;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Health check for upstream
        proxy_next_upstream error timeout http_500 http_502 http_503;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }

    # Block common attack paths
    location ~ /\.(git|env|htaccess) {
        deny all;
        return 404;
    }
}
```

### Nginx Stream (L4 / TCP/UDP)
```nginx
# /etc/nginx/nginx.conf (add to main context)
stream {
    upstream postgres {
        server db1:5432 weight=5;
        server db2:5432 weight=5;
        server db3:5432 backup;
    }

    upstream redis_cluster {
        hash $remote_addr consistent;
        server redis1:6379;
        server redis2:6379;
        server redis3:6379;
    }

    server {
        listen 5432;
        proxy_pass postgres;
        proxy_connect_timeout 3s;
        proxy_timeout 300s;
    }

    server {
        listen 6379;
        proxy_pass redis_cluster;
    }
}
```

## HAProxy

### Full Configuration
```haproxy
# /etc/haproxy/haproxy.cfg
global
    maxconn 50000
    log stdout format raw local0
    stats socket /var/run/haproxy.sock mode 660 level admin
    ssl-default-bind-ciphersuites TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets
    tune.ssl.default-dh-param 2048

defaults
    mode http
    log global
    option httplog
    option dontlognull
    option http-server-close
    option forwardfor
    timeout connect 5s
    timeout client 30s
    timeout server 30s
    timeout http-request 10s
    timeout http-keep-alive 10s
    timeout queue 30s
    errorfile 503 /etc/haproxy/errors/503.http

# Stats dashboard
frontend stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 10s
    stats auth admin:${STATS_PASSWORD}

# HTTP → HTTPS redirect
frontend http_front
    bind *:80
    http-request redirect scheme https unless { ssl_fc }

# HTTPS frontend
frontend https_front
    bind *:443 ssl crt /etc/haproxy/certs/example.com.pem alpn h2,http/1.1
    http-request set-header X-Forwarded-Proto https

    # ACL rules
    acl is_api path_beg /api/
    acl is_websocket hdr(Upgrade) -i websocket
    acl is_static path_beg /static/ /assets/ /images/
    acl is_health path /health

    # Rate limiting with stick tables
    stick-table type ip size 100k expire 30s store http_req_rate(10s)
    http-request track-sc0 src
    http-request deny deny_status 429 if { sc_http_req_rate(0) gt 100 }

    # Routing
    use_backend ws_servers if is_websocket
    use_backend api_servers if is_api
    use_backend static_servers if is_static
    default_backend app_servers

# Backends
backend app_servers
    balance leastconn
    option httpchk GET /health
    http-check expect status 200
    cookie SERVERID insert indirect nocache

    server app1 app1:8080 check inter 5s fall 3 rise 2 cookie app1 weight 100
    server app2 app2:8080 check inter 5s fall 3 rise 2 cookie app2 weight 100
    server app3 app3:8080 check inter 5s fall 3 rise 2 cookie app3 weight 50
    server app4 app4:8080 check inter 5s fall 3 rise 2 cookie app4 backup

backend api_servers
    balance leastconn
    option httpchk GET /api/health
    http-check expect status 200

    # Circuit breaker: mark server down after 3 consecutive failures
    default-server inter 3s fall 3 rise 2 slowstart 60s

    server api1 api1:3000 check weight 100
    server api2 api2:3000 check weight 100
    server api3 api3:3000 check weight 80

    # Retry on connection error or empty response
    retry-on conn-failure empty-response response-timeout
    retries 2

backend ws_servers
    balance source
    option httpchk GET /health
    timeout tunnel 3600s

    server ws1 ws1:8080 check
    server ws2 ws2:8080 check

backend static_servers
    balance roundrobin
    http-request set-header Cache-Control "public, max-age=31536000, immutable"

    server static1 static1:80 check
    server static2 static2:80 check
```

### HAProxy Docker Compose
```yaml
version: "3.8"

services:
  haproxy:
    image: haproxy:2.8-alpine
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
      - ./certs:/etc/haproxy/certs:ro
    ports:
      - "80:80"
      - "443:443"
      - "8404:8404"
    sysctls:
      - net.ipv4.ip_unprivileged_port_start=0
    restart: unless-stopped
```

## SSL / Let's Encrypt

### Certbot with Nginx
```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d example.com -d www.example.com

# Auto-renewal (crontab)
0 3 * * * certbot renew --quiet --post-hook "nginx -s reload"
```

### Self-Signed for Development
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/dev.key \
  -out /etc/ssl/certs/dev.crt \
  -subj "/CN=localhost"
```

## Health Check Patterns

### Active Health Checks (Nginx Plus / HAProxy)
```haproxy
# HAProxy — detailed health check
backend api_servers
    option httpchk
    http-check send meth GET uri /health ver HTTP/1.1 hdr Host example.com
    http-check expect rstatus ^(2|3)[0-9]{2}
```

### Passive Health Checks (Nginx OSS)
```nginx
upstream backend {
    server app1:8080 max_fails=3 fail_timeout=30s;
    server app2:8080 max_fails=3 fail_timeout=30s;

    # Nginx retries next upstream on these errors
    # (configured per-location with proxy_next_upstream)
}
```

## Load Balancing Algorithms

**Round Robin** — Default, equal distribution. Good for uniform servers.
```nginx
upstream backend { server a:80; server b:80; }
```

**Weighted Round Robin** — Unequal servers, send more to stronger ones.
```nginx
upstream backend { server a:80 weight=5; server b:80 weight=3; }
```

**Least Connections** — Route to server with fewest active connections. Best for variable request times.
```nginx
upstream backend { least_conn; server a:80; server b:80; }
```

**IP Hash** — Sticky sessions by client IP. Use for session affinity without cookies.
```nginx
upstream backend { ip_hash; server a:80; server b:80; }
```

**Consistent Hashing** — Minimize redistribution when servers change. Good for caches.
```nginx
upstream backend { hash $request_uri consistent; server a:80; server b:80; }
```

## Workflow

1. **Assess** — Map traffic patterns, identify backend services, define routing rules
2. **Configure** — Set up frontends (listeners), backends (server pools), routing ACLs
3. **Secure** — SSL termination, security headers, rate limiting, WAF rules
4. **Health Check** — Configure active/passive checks with appropriate intervals
5. **Test** — Verify failover, load distribution, WebSocket, and edge cases
6. **Monitor** — Track connection counts, response times, error rates, upstream health
7. **Tune** — Adjust timeouts, buffer sizes, worker counts based on traffic patterns

## Best Practices

- Terminate SSL at the load balancer — simpler cert management, offloads crypto from backends
- Always set `proxy_set_header X-Real-IP` and `X-Forwarded-For` — backends need real client IPs
- Use `least_conn` for APIs with variable response times, `round_robin` for uniform workloads
- Set `max_fails` and `fail_timeout` — don't keep sending traffic to dead backends
- Configure `proxy_next_upstream` to retry on 502/503 — transparent failover
- Use keepalive connections to backends (`keepalive 32`) — reduces TCP overhead
- Rate limit auth endpoints much more aggressively than general API
- Log `$upstream_response_time` separately from `$request_time` to isolate backend vs. network latency
- Use stick tables (HAProxy) or `limit_req_zone` (Nginx) for DDoS protection
- Health check endpoints should test real dependencies (DB, cache), not just return 200
