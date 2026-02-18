---
name: disaster-recovery
description: >-
  Design and implement backup strategies, disaster recovery plans, and business continuity procedures.
  Use when someone asks to "set up backups", "create DR plan", "configure database backups",
  "implement point-in-time recovery", "design failover architecture", "test disaster recovery",
  or "calculate RPO/RTO". Covers backup automation, replication, failover, and recovery testing.
license: Apache-2.0
compatibility: "PostgreSQL, MySQL, MongoDB, Redis, S3, rsync, Restic, Velero (Kubernetes)"
metadata:
  author: terminal-skills
  category: devops
  tags:
    - backup
    - disaster-recovery
    - failover
    - replication
    - business-continuity
    - devops
    - database
---

# Disaster Recovery

You are a reliability engineer specializing in backup strategies, disaster recovery planning, and business continuity. You design systems that survive failures gracefully and recover quickly, with tested, automated procedures.

## Core Concepts

**RPO (Recovery Point Objective)** — Maximum acceptable data loss measured in time. "We can afford to lose at most 1 hour of data."

**RTO (Recovery Time Objective)** — Maximum acceptable downtime. "We need to be back online within 30 minutes."

**DR Tiers:**
- **Tier 1 (Cold)** — Backups only. RTO: hours to days. RPO: last backup.
- **Tier 2 (Warm)** — Standby replicas, restored on demand. RTO: 30min–2h. RPO: minutes.
- **Tier 3 (Hot)** — Active replicas, automatic failover. RTO: seconds–minutes. RPO: near-zero.

## Database Backups

### PostgreSQL
```bash
#!/bin/bash
# pg-backup.sh — automated PostgreSQL backup with rotation

set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-myapp}"
DB_USER="${DB_USER:-postgres}"
BACKUP_DIR="/backups/postgresql"
S3_BUCKET="s3://backups-prod/postgresql"
RETENTION_DAYS=30
DATE=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of ${DB_NAME}..."

# Full backup with compression
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  --format=custom \
  --compress=9 \
  --verbose \
  --file="${BACKUP_FILE}"

# Verify backup integrity
pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1
echo "[$(date)] Backup verified: ${BACKUP_FILE} ($(du -sh "$BACKUP_FILE" | cut -f1))"

# Upload to S3
aws s3 cp "$BACKUP_FILE" "${S3_BUCKET}/${DB_NAME}_${DATE}.sql.gz" \
  --storage-class STANDARD_IA

# Clean up old local backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# Clean up old S3 backups (via lifecycle policy is preferred, but belt-and-suspenders)
aws s3 ls "${S3_BUCKET}/" | while read -r line; do
  file_date=$(echo "$line" | awk '{print $1}')
  file_name=$(echo "$line" | awk '{print $4}')
  if [[ $(date -d "$file_date" +%s) -lt $(date -d "-${RETENTION_DAYS} days" +%s) ]]; then
    aws s3 rm "${S3_BUCKET}/${file_name}"
  fi
done

echo "[$(date)] Backup complete."
```

**PostgreSQL WAL Archiving (Point-in-Time Recovery)**
```ini
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://backups-prod/wal/%f'
archive_timeout = 300
```

```bash
# Restore to specific point in time
pg_restore --dbname=myapp_recovered backup.sql.gz

# Then apply WAL logs up to target time
cat > /tmp/recovery.conf << EOF
restore_command = 'aws s3 cp s3://backups-prod/wal/%f %p'
recovery_target_time = '2024-01-15 14:30:00 UTC'
recovery_target_action = 'promote'
EOF
```

### MySQL
```bash
#!/bin/bash
# mysql-backup.sh

set -euo pipefail

DB_NAME="${DB_NAME:-myapp}"
BACKUP_DIR="/backups/mysql"
DATE=$(date +%Y-%m-%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Full backup with mysqldump
mysqldump \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --set-gtid-purged=OFF \
  --databases "$DB_NAME" | gzip > "${BACKUP_DIR}/${DB_NAME}_${DATE}.sql.gz"

# Or use xtrabackup for large databases (non-blocking)
# xtrabackup --backup --target-dir="${BACKUP_DIR}/full_${DATE}" \
#   --compress --compress-threads=4
```

**MySQL Binary Log Replication**
```ini
# my.cnf — Primary
[mysqld]
server-id = 1
log-bin = mysql-bin
binlog-format = ROW
expire-logs-days = 7
sync-binlog = 1
```

### MongoDB
```bash
#!/bin/bash
# mongo-backup.sh

set -euo pipefail

BACKUP_DIR="/backups/mongodb"
DATE=$(date +%Y-%m-%d_%H%M%S)

# Full backup with oplog for point-in-time recovery
mongodump \
  --uri="mongodb://user:pass@localhost:27017" \
  --db=myapp \
  --oplog \
  --gzip \
  --out="${BACKUP_DIR}/${DATE}"

# Upload to S3
aws s3 sync "${BACKUP_DIR}/${DATE}" "s3://backups-prod/mongodb/${DATE}/" \
  --storage-class STANDARD_IA
```

### Redis
```bash
#!/bin/bash
# redis-backup.sh

# Trigger RDB snapshot
redis-cli BGSAVE

# Wait for completion
while [ "$(redis-cli LASTSAVE)" == "$LAST_SAVE" ]; do
  sleep 1
done

# Copy dump file
cp /var/lib/redis/dump.rdb "/backups/redis/dump_$(date +%Y%m%d_%H%M%S).rdb"

# For AOF persistence (append-only file)
# redis-cli BGREWRITEAOF
```

## Restic — Universal Backup Tool

```bash
# Initialize repository (S3, local, SFTP, etc.)
export RESTIC_REPOSITORY="s3:s3.amazonaws.com/backups-prod/restic"
export RESTIC_PASSWORD="your-encryption-password"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."

restic init

# Backup with tags
restic backup /var/www/app /etc/nginx /home/deploy \
  --tag app,config \
  --exclude-file=/etc/restic/excludes.txt \
  --verbose

# List snapshots
restic snapshots

# Restore specific snapshot
restic restore latest --target /tmp/restore --include "/var/www/app"

# Restore specific file
restic dump latest /etc/nginx/nginx.conf > /tmp/nginx.conf

# Prune old backups (keep policy)
restic forget \
  --keep-hourly 24 \
  --keep-daily 30 \
  --keep-weekly 12 \
  --keep-monthly 24 \
  --prune

# Check repository integrity
restic check --read-data
```

**Restic Cron Schedule**
```bash
# /etc/cron.d/restic-backup
# Hourly app backup
0 * * * * root /usr/local/bin/restic-backup.sh app >> /var/log/restic-app.log 2>&1
# Daily full backup at 3 AM
0 3 * * * root /usr/local/bin/restic-backup.sh full >> /var/log/restic-full.log 2>&1
# Weekly prune on Sunday at 4 AM
0 4 * * 0 root /usr/local/bin/restic-prune.sh >> /var/log/restic-prune.log 2>&1
# Monthly integrity check
0 5 1 * * root restic check --read-data >> /var/log/restic-check.log 2>&1
```

## Kubernetes — Velero

```bash
# Install Velero with S3 backend
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.9.0 \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config region=us-east-1

# Backup entire namespace
velero backup create app-backup \
  --include-namespaces production \
  --snapshot-volumes \
  --ttl 720h

# Scheduled backup
velero schedule create daily-backup \
  --schedule="0 3 * * *" \
  --include-namespaces production,staging \
  --snapshot-volumes \
  --ttl 720h

# Restore
velero restore create --from-backup app-backup

# Restore to different namespace
velero restore create --from-backup app-backup \
  --namespace-mappings production:dr-recovery

# Check backup status
velero backup describe app-backup --details
velero backup logs app-backup
```

## Failover Architectures

### PostgreSQL Streaming Replication
```ini
# Primary — postgresql.conf
wal_level = replica
max_wal_senders = 5
wal_keep_size = 1GB
synchronous_standby_names = 'standby1'

# Primary — pg_hba.conf
host replication replicator standby_ip/32 scram-sha-256
```

```bash
# Standby setup
pg_basebackup -h primary_host -U replicator -D /var/lib/postgresql/data -Fp -Xs -R -P

# standby.signal file is created by -R flag
# primary_conninfo is set in postgresql.auto.conf
```

### Automated Failover with Patroni
```yaml
# patroni.yml
scope: postgres-cluster
name: node1

restapi:
  listen: 0.0.0.0:8008
  connect_address: node1:8008

etcd3:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    synchronous_mode: true
    postgresql:
      use_pg_rewind: true
      parameters:
        max_connections: 200
        shared_buffers: 2GB
        wal_level: replica
        max_wal_senders: 5

  initdb:
    - encoding: UTF8
    - data-checksums

postgresql:
  listen: 0.0.0.0:5432
  connect_address: node1:5432
  data_dir: /var/lib/postgresql/data
  authentication:
    superuser:
      username: postgres
      password: ${POSTGRES_PASSWORD}
    replication:
      username: replicator
      password: ${REPLICATION_PASSWORD}
```

### Redis Sentinel
```conf
# sentinel.conf
sentinel monitor mymaster redis-primary 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1

sentinel auth-pass mymaster ${REDIS_PASSWORD}
sentinel auth-user mymaster sentinel-user
```

## DR Testing

### Recovery Test Script
```bash
#!/bin/bash
# dr-test.sh — Monthly disaster recovery drill

set -euo pipefail

LOG="/var/log/dr-test-$(date +%Y%m%d).log"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
notify() { curl -s -X POST "$SLACK_WEBHOOK" -d "{\"text\": \"🔥 DR Test: $1\"}"; }

log "=== DR TEST STARTED ==="
notify "DR test starting"

# 1. Verify backup exists and is recent
LATEST_BACKUP=$(aws s3 ls s3://backups-prod/postgresql/ --recursive | sort | tail -1)
BACKUP_AGE_HOURS=$(( ($(date +%s) - $(date -d "$(echo $LATEST_BACKUP | awk '{print $1" "$2}')" +%s)) / 3600 ))

if [ "$BACKUP_AGE_HOURS" -gt 25 ]; then
  log "FAIL: Latest backup is ${BACKUP_AGE_HOURS}h old (threshold: 24h)"
  notify "❌ FAIL: Backup too old (${BACKUP_AGE_HOURS}h)"
  exit 1
fi
log "PASS: Backup age ${BACKUP_AGE_HOURS}h"

# 2. Download and restore to test instance
log "Downloading latest backup..."
BACKUP_FILE=$(echo "$LATEST_BACKUP" | awk '{print $4}')
aws s3 cp "s3://backups-prod/postgresql/${BACKUP_FILE}" /tmp/dr-test-backup.sql.gz

log "Restoring to test database..."
dropdb --if-exists dr_test_db
createdb dr_test_db
pg_restore -d dr_test_db /tmp/dr-test-backup.sql.gz

# 3. Run validation queries
RECORD_COUNT=$(psql -d dr_test_db -t -c "SELECT count(*) FROM users;")
if [ "$RECORD_COUNT" -lt 1 ]; then
  log "FAIL: Restored database has no users"
  notify "❌ FAIL: Empty database after restore"
  exit 1
fi
log "PASS: Database restored with ${RECORD_COUNT} users"

# 4. Measure recovery time
RESTORE_DURATION=$SECONDS
log "Recovery completed in ${RESTORE_DURATION}s"

# 5. Cleanup
dropdb dr_test_db
rm /tmp/dr-test-backup.sql.gz

log "=== DR TEST PASSED ==="
notify "✅ DR test passed. RPO: ${BACKUP_AGE_HOURS}h, RTO: ${RESTORE_DURATION}s, Records: ${RECORD_COUNT}"
```

## DR Plan Template

```markdown
# Disaster Recovery Plan

## Service: [App Name]
## Last Updated: [Date]
## Last Tested: [Date]

### Objectives
- RPO: 1 hour (max data loss)
- RTO: 30 minutes (max downtime)

### Backup Schedule
| Component    | Method      | Frequency | Retention | Location           |
|-------------|-------------|-----------|-----------|-------------------|
| PostgreSQL  | pg_dump     | Hourly    | 30 days   | S3 us-east-1      |
| PostgreSQL  | WAL archive | Continuous| 7 days    | S3 us-east-1      |
| Redis       | RDB snapshot| Every 6h  | 7 days    | S3 us-east-1      |
| App config  | Restic      | Daily     | 90 days   | S3 us-west-2      |
| Secrets     | Vault snap  | Daily     | 90 days   | S3 eu-west-1      |

### Failover Procedures
1. **Database failure** → Patroni auto-failover (< 30s)
2. **Region failure** → DNS failover to DR region (< 5min)
3. **Data corruption** → Restore from backup + WAL replay

### Recovery Steps
1. Identify scope of failure
2. Notify stakeholders (Slack #incidents)
3. Execute relevant failover procedure
4. Verify service health
5. Begin post-incident review

### Contacts
- Primary on-call: [Name] ([Phone])
- Secondary: [Name] ([Phone])
- VP Engineering: [Name] ([Phone])
```

## Workflow

1. **Assess** — Identify critical systems, define RPO/RTO per service
2. **Design** — Choose DR tier per component based on business impact
3. **Implement** — Set up automated backups, replication, failover mechanisms
4. **Verify** — Validate backup integrity after every backup run
5. **Test** — Run monthly DR drills, measure actual RTO
6. **Document** — Maintain runbooks with step-by-step recovery procedures
7. **Review** — Quarterly review of DR plan against infrastructure changes

## Best Practices

- **Test restores regularly** — untested backups are not backups
- **3-2-1 rule**: 3 copies, 2 different media types, 1 offsite
- Encrypt backups at rest and in transit
- Monitor backup jobs — alert on failure, not just success
- Store DR runbooks outside the systems they recover (printed copy, separate cloud)
- Automate everything — manual steps under pressure lead to errors
- Measure actual RTO during drills, not theoretical RTO
- Include secrets/credentials in DR plan — you can't recover without them
- Version your backup scripts alongside application code
- Calculate cost of downtime to justify DR investment
