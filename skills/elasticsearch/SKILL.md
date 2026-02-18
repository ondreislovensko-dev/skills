---
name: elasticsearch
description: >-
  Deploy, configure, and manage Elasticsearch clusters for search, logging, and analytics.
  Use when someone asks to "set up Elasticsearch", "build search", "configure ELK stack",
  "optimize search queries", "set up log aggregation", "manage indices", or "tune cluster performance".
  Covers index design, mappings, queries (DSL), aggregations, cluster management, and the ELK/EFK stack.
license: Apache-2.0
compatibility: "Elasticsearch 8.x, Kibana 8.x, Logstash 8.x, Filebeat, OpenSearch"
metadata:
  author: terminal-skills
  category: database
  tags:
    - elasticsearch
    - search
    - elk-stack
    - logging
    - kibana
    - logstash
    - full-text-search
    - analytics
---

# Elasticsearch

You are a search and analytics expert specializing in Elasticsearch. You design indices, write efficient queries, configure clusters, and build search-powered features from log aggregation to product search to real-time analytics.

## Cluster Setup

### Docker Compose — ELK Stack
```yaml
version: "3.8"

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-changeme}
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.http.ssl.enabled=false
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    ulimits:
      memlock:
        soft: -1
        hard: -1
    healthcheck:
      test: ["CMD-SHELL", "curl -s -u elastic:${ELASTIC_PASSWORD:-changeme} http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\\|yellow\"'"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:8.13.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD:-changeme}
    ports:
      - "5601:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

  logstash:
    image: docker.elastic.co/logstash/logstash:8.13.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    environment:
      - "LS_JAVA_OPTS=-Xms512m -Xmx512m"
    depends_on:
      elasticsearch:
        condition: service_healthy

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.13.0
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/log:/var/log:ro
    depends_on:
      elasticsearch:
        condition: service_healthy

volumes:
  es_data:
```

### Production Cluster (3-node)
```yaml
# docker-compose.prod.yml
services:
  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - node.name=es01
      - cluster.name=production
      - discovery.seed_hosts=es02,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - node.roles=master,data_hot,ingest
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"
      - xpack.security.enabled=true
    volumes:
      - es01_data:/usr/share/elasticsearch/data

  es02:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - node.name=es02
      - cluster.name=production
      - discovery.seed_hosts=es01,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - node.roles=data_warm,data_content
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"
    volumes:
      - es02_data:/usr/share/elasticsearch/data

  es03:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - node.name=es03
      - cluster.name=production
      - discovery.seed_hosts=es01,es02
      - cluster.initial_master_nodes=es01,es02,es03
      - node.roles=data_cold,ml
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
    volumes:
      - es03_data:/usr/share/elasticsearch/data
```

## Index Design

### Mappings
```json
PUT /products
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "product_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "synonym_filter", "stemmer"]
        },
        "autocomplete_analyzer": {
          "type": "custom",
          "tokenizer": "autocomplete_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "autocomplete_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 15,
          "token_chars": ["letter", "digit"]
        }
      },
      "filter": {
        "synonym_filter": {
          "type": "synonym",
          "synonyms": [
            "laptop, notebook",
            "phone, mobile, smartphone",
            "tv, television"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "product_analyzer",
        "fields": {
          "keyword": { "type": "keyword" },
          "autocomplete": { "type": "text", "analyzer": "autocomplete_analyzer", "search_analyzer": "standard" }
        }
      },
      "description": {
        "type": "text",
        "analyzer": "product_analyzer"
      },
      "category": { "type": "keyword" },
      "price": { "type": "float" },
      "in_stock": { "type": "boolean" },
      "rating": { "type": "float" },
      "tags": { "type": "keyword" },
      "created_at": { "type": "date" },
      "location": { "type": "geo_point" },
      "metadata": { "type": "object", "enabled": false }
    }
  }
}
```

### Index Templates (for logs)
```json
PUT /_index_template/logs
{
  "index_patterns": ["logs-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 1,
      "index.lifecycle.name": "logs-policy",
      "index.lifecycle.rollover_alias": "logs"
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "service": { "type": "keyword" },
        "message": { "type": "text" },
        "trace_id": { "type": "keyword" },
        "host": { "type": "keyword" },
        "response_time_ms": { "type": "integer" }
      }
    }
  }
}
```

### Index Lifecycle Management
```json
PUT /_ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": { "snapshot_repository": "backups" },
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

## Query DSL

### Full-Text Search
```json
GET /products/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "wireless noise cancelling headphones",
            "fields": ["name^3", "description", "tags^2"],
            "type": "best_fields",
            "fuzziness": "AUTO"
          }
        }
      ],
      "filter": [
        { "term": { "in_stock": true } },
        { "range": { "price": { "gte": 50, "lte": 300 } } },
        { "terms": { "category": ["electronics", "audio"] } }
      ],
      "should": [
        { "range": { "rating": { "gte": 4.0, "boost": 2 } } },
        { "term": { "tags": { "value": "bestseller", "boost": 1.5 } } }
      ],
      "minimum_should_match": 0
    }
  },
  "highlight": {
    "fields": {
      "name": {},
      "description": { "fragment_size": 150, "number_of_fragments": 3 }
    }
  },
  "sort": [
    { "_score": "desc" },
    { "rating": "desc" }
  ],
  "from": 0,
  "size": 20
}
```

### Autocomplete
```json
GET /products/_search
{
  "query": {
    "multi_match": {
      "query": "wire",
      "fields": ["name.autocomplete"],
      "type": "bool_prefix"
    }
  },
  "size": 10,
  "_source": ["name", "category", "price"]
}
```

### Aggregations
```json
GET /products/_search
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": { "field": "category", "size": 20 },
      "aggs": {
        "avg_price": { "avg": { "field": "price" } },
        "price_ranges": {
          "range": {
            "field": "price",
            "ranges": [
              { "to": 50 },
              { "from": 50, "to": 200 },
              { "from": 200 }
            ]
          }
        }
      }
    },
    "price_histogram": {
      "histogram": { "field": "price", "interval": 50 }
    },
    "avg_rating": { "avg": { "field": "rating" } }
  }
}
```

### Log Search with Aggregation
```json
GET /logs-*/_search
{
  "query": {
    "bool": {
      "must": [
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ],
      "filter": [
        { "term": { "level": "error" } }
      ]
    }
  },
  "aggs": {
    "errors_over_time": {
      "date_histogram": {
        "field": "@timestamp",
        "fixed_interval": "5m"
      }
    },
    "by_service": {
      "terms": { "field": "service", "size": 10 }
    },
    "slow_requests": {
      "percentiles": {
        "field": "response_time_ms",
        "percents": [50, 90, 95, 99]
      }
    }
  },
  "sort": [{ "@timestamp": "desc" }],
  "size": 50
}
```

## Logstash Pipeline

```ruby
# logstash/pipeline/main.conf
input {
  beats {
    port => 5044
  }

  tcp {
    port => 5000
    codec => json_lines
  }
}

filter {
  if [type] == "nginx" {
    grok {
      match => { "message" => '%{IPORHOST:remote_addr} - %{DATA:remote_user} \[%{HTTPDATE:time_local}\] "%{WORD:method} %{URIPATHPARAM:request} HTTP/%{NUMBER:http_version}" %{NUMBER:status} %{NUMBER:body_bytes_sent} "%{DATA:http_referer}" "%{DATA:http_user_agent}"' }
    }
    date {
      match => ["time_local", "dd/MMM/yyyy:HH:mm:ss Z"]
    }
    mutate {
      convert => { "status" => "integer" "body_bytes_sent" => "integer" }
    }
    geoip {
      source => "remote_addr"
    }
  }

  if [type] == "app" {
    json {
      source => "message"
    }
    date {
      match => ["timestamp", "ISO8601"]
    }
  }

  # Drop health check noise
  if [request] =~ /^\/health/ {
    drop {}
  }

  # Add environment tag
  mutate {
    add_field => { "environment" => "${ENVIRONMENT:production}" }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    user => "elastic"
    password => "${ELASTIC_PASSWORD}"
    index => "logs-%{[type]}-%{+YYYY.MM.dd}"
  }
}
```

## Filebeat Configuration

```yaml
# filebeat.yml
filebeat.inputs:
  - type: container
    paths:
      - /var/lib/docker/containers/*/*.log
    processors:
      - add_docker_metadata: ~

  - type: log
    paths:
      - /var/log/nginx/access.log
    fields:
      type: nginx
    fields_under_root: true

  - type: log
    paths:
      - /var/log/app/*.json
    fields:
      type: app
    fields_under_root: true
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  username: "elastic"
  password: "${ELASTIC_PASSWORD}"
  indices:
    - index: "logs-nginx-%{+yyyy.MM.dd}"
      when.equals:
        fields.type: "nginx"
    - index: "logs-app-%{+yyyy.MM.dd}"
      when.equals:
        fields.type: "app"

setup.kibana:
  host: "kibana:5601"
```

## Cluster Operations

### Health & Status
```bash
# Cluster health
curl -s localhost:9200/_cluster/health?pretty

# Node stats
curl -s localhost:9200/_nodes/stats?pretty

# Index stats
curl -s localhost:9200/_cat/indices?v&s=store.size:desc

# Shard allocation
curl -s localhost:9200/_cat/shards?v&s=state

# Pending tasks
curl -s localhost:9200/_cluster/pending_tasks?pretty
```

### Performance Tuning
```json
// Bulk indexing optimization
PUT /logs-2024.01.01/_settings
{
  "index": {
    "refresh_interval": "30s",
    "number_of_replicas": 0,
    "translog.durability": "async",
    "translog.flush_threshold_size": "1gb"
  }
}

// After bulk load, restore settings
PUT /logs-2024.01.01/_settings
{
  "index": {
    "refresh_interval": "1s",
    "number_of_replicas": 1,
    "translog.durability": "request"
  }
}

// Force merge read-only indices
POST /logs-2024.01.01/_forcemerge?max_num_segments=1
```

### Snapshot & Restore
```json
// Register repository
PUT /_snapshot/s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "elasticsearch-backups",
    "region": "us-east-1",
    "base_path": "production"
  }
}

// Create snapshot
PUT /_snapshot/s3_backup/snapshot_2024_01
{
  "indices": "logs-*,products",
  "ignore_unavailable": true,
  "include_global_state": false
}

// Restore
POST /_snapshot/s3_backup/snapshot_2024_01/_restore
{
  "indices": "products",
  "rename_pattern": "(.+)",
  "rename_replacement": "restored_$1"
}
```

## Workflow

1. **Design** — Define index mappings based on query patterns (search-first design)
2. **Configure** — Set up cluster, node roles, shard strategy
3. **Ingest** — Configure Logstash/Filebeat pipelines or direct API ingestion
4. **Query** — Write DSL queries optimized for your use case
5. **Aggregate** — Build analytics with aggregation pipelines
6. **Lifecycle** — Set up ILM policies for automatic index rotation and cleanup
7. **Monitor** — Track cluster health, shard balance, query performance

## Best Practices

- Design mappings before indexing — schema changes on existing indices are expensive
- Use `keyword` for filtering/sorting, `text` for full-text search — use multi-fields for both
- Keep shard size between 10-50GB for optimal performance
- Use ILM to manage index lifecycle — don't let old indices eat resources
- Avoid deep pagination (`from` + `size` > 10000) — use `search_after` or scroll API
- Use `_source` filtering to return only needed fields
- Cache expensive aggregations with `request_cache`
- For logs: use data streams instead of manual index-per-day
- Monitor cluster with `_cat` APIs and set up alerts for yellow/red status
