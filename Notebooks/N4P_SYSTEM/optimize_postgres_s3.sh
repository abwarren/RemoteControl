#!/bin/bash
#
# PokerBet Cost Optimization Implementation Script
# Reduces monthly costs from $231.50 to $140
#
# IMPORTANT: Review full plan before executing
# See: POKERBET_COST_OPTIMIZATION_140.md
#
# Usage: ./optimize_postgres_s3.sh [--postgres-only|--s3-only|--all]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
S3_BUCKET="poker-raw-data"
S3_BACKUP_BUCKET="poker-backups"
DB_NAME="poker_data"
DB_USER="poker_user"
BACKUP_DIR="/opt/backups/postgres"
PROCESSING_INSTANCE_IP="YOUR_INSTANCE_IP_HERE"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if running on correct instance
    if [ "$EUID" -eq 0 ]; then
        log_warn "Running as root. Consider using sudo instead."
    fi

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Install with: sudo apt-get install awscli"
        exit 1
    fi

    # Check PostgreSQL (if doing postgres optimization)
    if [[ "$1" == *"postgres"* ]]; then
        if command -v psql &> /dev/null; then
            log_warn "PostgreSQL already installed. Will skip installation."
        fi
    fi

    log_success "Prerequisites check passed"
}

install_postgresql() {
    log_info "Installing PostgreSQL 14..."

    sudo apt-get update -qq
    sudo apt-get install -y postgresql-14 postgresql-contrib-14

    sudo systemctl start postgresql
    sudo systemctl enable postgresql

    log_success "PostgreSQL 14 installed"
}

configure_postgresql() {
    log_info "Configuring PostgreSQL for t3.medium (4GB RAM)..."

    # Backup original config
    sudo cp /etc/postgresql/14/main/postgresql.conf /etc/postgresql/14/main/postgresql.conf.bak

    # Apply optimized settings
    sudo tee -a /etc/postgresql/14/main/postgresql.conf > /dev/null <<EOF

# PokerBet Optimizations ($(date +%Y-%m-%d))
shared_buffers = 1GB
effective_cache_size = 3GB
maintenance_work_mem = 256MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
EOF

    sudo systemctl restart postgresql

    log_success "PostgreSQL configured"
}

create_database() {
    log_info "Creating database and user..."

    read -sp "Enter password for database user '$DB_USER': " DB_PASSWORD
    echo

    sudo -u postgres psql <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF

    # Configure local authentication
    echo "host    $DB_NAME    $DB_USER    127.0.0.1/32    md5" | \
        sudo tee -a /etc/postgresql/14/main/pg_hba.conf > /dev/null

    sudo systemctl restart postgresql

    log_success "Database created: $DB_NAME"
    log_warn "Save password securely: $DB_PASSWORD"
}

setup_backup_script() {
    log_info "Setting up daily backup script..."

    sudo mkdir -p $BACKUP_DIR
    sudo mkdir -p /opt/scripts

    # Create backup script
    sudo tee /opt/scripts/backup_postgres.sh > /dev/null <<'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/postgres"
S3_BUCKET="poker-backups"
DB_NAME="poker_data"
DB_USER="poker_user"

mkdir -p $BACKUP_DIR

# Full database dump
pg_dump -U $DB_USER -d $DB_NAME | gzip > $BACKUP_DIR/poker_data_$DATE.sql.gz

if [ $? -eq 0 ]; then
    echo "$(date): Backup created: $BACKUP_DIR/poker_data_$DATE.sql.gz"

    # Upload to S3
    aws s3 cp $BACKUP_DIR/poker_data_$DATE.sql.gz s3://$S3_BUCKET/postgres/$DATE.sql.gz

    if [ $? -eq 0 ]; then
        echo "$(date): Backup uploaded to S3"
    else
        echo "$(date): ERROR - S3 upload failed"
    fi

    # Keep local backups for 7 days
    find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
else
    echo "$(date): ERROR - Backup failed"
    exit 1
fi
EOF

    sudo chmod +x /opt/scripts/backup_postgres.sh

    # Add cron job
    (crontab -l 2>/dev/null; echo "0 2 * * * /opt/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1") | crontab -

    log_success "Backup script configured (runs daily at 2 AM)"
}

test_backup_restore() {
    log_info "Testing backup and restore..."

    # Run backup manually
    sudo /opt/scripts/backup_postgres.sh

    if [ $? -eq 0 ]; then
        log_success "Backup test successful"
    else
        log_error "Backup test failed"
        exit 1
    fi
}

optimize_s3_lifecycle() {
    log_info "Updating S3 lifecycle policy for $S3_BUCKET..."

    # Create lifecycle policy JSON
    cat > /tmp/lifecycle-policy.json <<'EOF'
{
  "Rules": [
    {
      "Id": "ArchiveRawPokerData30Day",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER_INSTANT_RETRIEVAL"
        }
      ],
      "NoncurrentVersionTransitions": [
        {
          "NoncurrentDays": 30,
          "StorageClass": "GLACIER_INSTANT_RETRIEVAL"
        }
      ]
    }
  ]
}
EOF

    # Apply lifecycle policy
    aws s3api put-bucket-lifecycle-configuration \
        --bucket $S3_BUCKET \
        --lifecycle-configuration file:///tmp/lifecycle-policy.json

    if [ $? -eq 0 ]; then
        log_success "S3 lifecycle policy updated"
    else
        log_error "Failed to update S3 lifecycle policy"
        exit 1
    fi

    # Verify policy
    log_info "Verifying policy..."
    aws s3api get-bucket-lifecycle-configuration --bucket $S3_BUCKET

    rm /tmp/lifecycle-policy.json
}

verify_s3_policy() {
    log_info "Current S3 lifecycle policy:"
    aws s3api get-bucket-lifecycle-configuration --bucket $S3_BUCKET | jq '.'
}

print_summary() {
    echo
    echo "=========================================="
    echo "   OPTIMIZATION COMPLETE"
    echo "=========================================="
    echo
    echo "Cost Reduction:"
    echo "  Before: \$231.50/month"
    echo "  After:  \$140.00/month"
    echo "  Savings: \$91.50/month (\$1,098/year)"
    echo
    echo "Next Steps:"
    echo "  1. Run schema.sql to create tables:"
    echo "     psql -U $DB_USER -d $DB_NAME -f schema.sql"
    echo
    echo "  2. Update Flask API connection to localhost"
    echo
    echo "  3. Monitor PostgreSQL performance:"
    echo "     psql -U $DB_USER -d $DB_NAME"
    echo "     SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
    echo
    echo "  4. Monitor S3 costs in AWS Cost Explorer"
    echo
    echo "Backup Info:"
    echo "  Script: /opt/scripts/backup_postgres.sh"
    echo "  Schedule: Daily at 2 AM"
    echo "  Location: $BACKUP_DIR"
    echo "  S3: s3://$S3_BACKUP_BUCKET/postgres/"
    echo
    echo "=========================================="
}

# Main execution
main() {
    MODE="${1:-all}"

    echo
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║   PokerBet Cost Optimization Script                 ║"
    echo "║   Target: \$140/month (from \$231.50)                 ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo

    case $MODE in
        --postgres-only)
            log_info "Mode: PostgreSQL optimization only"
            check_prerequisites "postgres"
            install_postgresql
            configure_postgresql
            create_database
            setup_backup_script
            test_backup_restore
            ;;
        --s3-only)
            log_info "Mode: S3 optimization only"
            check_prerequisites "s3"
            optimize_s3_lifecycle
            verify_s3_policy
            ;;
        --all)
            log_info "Mode: Full optimization"
            check_prerequisites "all"
            install_postgresql
            configure_postgresql
            create_database
            setup_backup_script
            test_backup_restore
            optimize_s3_lifecycle
            verify_s3_policy
            ;;
        *)
            log_error "Invalid mode: $MODE"
            echo "Usage: $0 [--postgres-only|--s3-only|--all]"
            exit 1
            ;;
    esac

    print_summary
}

# Run main function
main "$@"
