#!/bin/bash
# =============================================================================
# Brain Capital - PostgreSQL Database Backup Script
# =============================================================================
# This script creates compressed backups of the PostgreSQL database
# and automatically rotates old backups (keeps last 7 days).
#
# USAGE:
#   ./backup_db.sh                    # Run backup manually
#   ./backup_db.sh --upload-s3        # Backup and upload to S3
#   ./backup_db.sh --upload-gdrive    # Backup and upload to Google Drive
#
# CRONTAB SETUP (run daily at 2 AM):
#   0 2 * * * /opt/brain-capital/backup_db.sh >> /var/log/brain-capital-backup.log 2>&1
#
# REQUIREMENTS:
#   - Docker and docker-compose running
#   - aws-cli installed and configured (for S3 uploads)
#   - rclone installed and configured (for Google Drive uploads)
#
# ENVIRONMENT VARIABLES (optional, or set below):
#   - BACKUP_DIR: Where to store backups (default: ./backups)
#   - RETENTION_DAYS: How many days to keep backups (default: 7)
#   - S3_BUCKET: S3 bucket name for cloud backups
#   - GDRIVE_REMOTE: rclone remote name for Google Drive (default: gdrive)
# =============================================================================

set -e  # Exit on any error

# ==================== CONFIGURATION ====================

# Get script directory (where docker-compose.yml is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Backup configuration
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE_ONLY=$(date +"%Y%m%d")

# Database configuration (from docker-compose.yml)
DB_CONTAINER="brain_capital_db"
DB_NAME="brain_capital"
DB_USER="brain_capital"

# Cloud storage configuration
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-brain-capital-backups}"
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_FOLDER="${GDRIVE_FOLDER:-brain-capital-backups}"

# Backup filenames
BACKUP_FILENAME="brain_capital_${TIMESTAMP}.sql"
BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILENAME"
COMPRESSED_FILE="$BACKUP_FILE.gz"

# ==================== FUNCTIONS ====================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        log "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
}

check_docker() {
    if ! docker ps &> /dev/null; then
        error "Docker is not running or not accessible"
        exit 1
    fi
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        error "Database container '$DB_CONTAINER' is not running"
        exit 1
    fi
    
    log "✅ Docker and database container are running"
}

create_backup() {
    log "📦 Creating database backup..."
    
    # Dump the database using pg_dump inside the container
    docker exec -t "$DB_CONTAINER" pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-privileges \
        --format=plain \
        > "$BACKUP_FILE"
    
    if [ ! -s "$BACKUP_FILE" ]; then
        error "Backup file is empty or was not created"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✅ Database dump created: $BACKUP_SIZE"
}

compress_backup() {
    log "🗜️  Compressing backup..."
    
    gzip -f "$BACKUP_FILE"
    
    if [ ! -f "$COMPRESSED_FILE" ]; then
        error "Compression failed"
        exit 1
    fi
    
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    log "✅ Backup compressed: $COMPRESSED_SIZE"
}

rotate_backups() {
    log "🔄 Rotating old backups (keeping last $RETENTION_DAYS days)..."
    
    # Count backups before rotation
    BEFORE_COUNT=$(find "$BACKUP_DIR" -name "brain_capital_*.sql.gz" -type f | wc -l)
    
    # Delete backups older than RETENTION_DAYS
    find "$BACKUP_DIR" -name "brain_capital_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
    
    # Count backups after rotation
    AFTER_COUNT=$(find "$BACKUP_DIR" -name "brain_capital_*.sql.gz" -type f | wc -l)
    DELETED=$((BEFORE_COUNT - AFTER_COUNT))
    
    if [ $DELETED -gt 0 ]; then
        log "✅ Removed $DELETED old backup(s)"
    else
        log "✅ No old backups to remove"
    fi
    
    log "📊 Current backups: $AFTER_COUNT"
}

upload_to_s3() {
    if [ -z "$S3_BUCKET" ]; then
        log "⏭️  S3 upload skipped (S3_BUCKET not configured)"
        return 0
    fi
    
    log "☁️  Uploading to S3: s3://$S3_BUCKET/$S3_PREFIX/"
    
    if ! command -v aws &> /dev/null; then
        error "aws-cli is not installed. Install with: pip install awscli"
        return 1
    fi
    
    aws s3 cp "$COMPRESSED_FILE" "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILENAME.gz" \
        --storage-class STANDARD_IA
    
    log "✅ Uploaded to S3 successfully"
    
    # Clean up old S3 backups (keep last RETENTION_DAYS)
    log "🔄 Cleaning old S3 backups..."
    aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | while read -r line; do
        file_date=$(echo "$line" | awk '{print $1}')
        file_name=$(echo "$line" | awk '{print $4}')
        
        if [ -n "$file_name" ]; then
            file_age=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
            if [ $file_age -gt $RETENTION_DAYS ]; then
                log "  Deleting old S3 backup: $file_name"
                aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$file_name"
            fi
        fi
    done
}

upload_to_gdrive() {
    log "☁️  Uploading to Google Drive: $GDRIVE_REMOTE:$GDRIVE_FOLDER/"
    
    if ! command -v rclone &> /dev/null; then
        error "rclone is not installed. Install from: https://rclone.org/install/"
        return 1
    fi
    
    # Check if remote is configured
    if ! rclone listremotes | grep -q "^${GDRIVE_REMOTE}:$"; then
        error "rclone remote '$GDRIVE_REMOTE' is not configured"
        error "Run: rclone config to set up Google Drive"
        return 1
    fi
    
    # Create folder if it doesn't exist
    rclone mkdir "$GDRIVE_REMOTE:$GDRIVE_FOLDER" 2>/dev/null || true
    
    # Upload the backup
    rclone copy "$COMPRESSED_FILE" "$GDRIVE_REMOTE:$GDRIVE_FOLDER/" --progress
    
    log "✅ Uploaded to Google Drive successfully"
    
    # Clean up old Google Drive backups (keep last RETENTION_DAYS)
    log "🔄 Cleaning old Google Drive backups..."
    rclone delete "$GDRIVE_REMOTE:$GDRIVE_FOLDER/" \
        --min-age "${RETENTION_DAYS}d" \
        --include "brain_capital_*.sql.gz"
    
    log "✅ Old Google Drive backups cleaned"
}

show_summary() {
    log ""
    log "=========================================="
    log "📋 BACKUP SUMMARY"
    log "=========================================="
    log "Backup file: $COMPRESSED_FILE"
    log "Size: $(du -h "$COMPRESSED_FILE" | cut -f1)"
    log "Retention: $RETENTION_DAYS days"
    log ""
    log "Local backups:"
    ls -lh "$BACKUP_DIR"/brain_capital_*.sql.gz 2>/dev/null | tail -5
    log "=========================================="
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --upload-s3      Upload backup to Amazon S3"
    echo "  --upload-gdrive  Upload backup to Google Drive"
    echo "  --upload-all     Upload to both S3 and Google Drive"
    echo "  --help           Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR       Backup directory (default: ./backups)"
    echo "  RETENTION_DAYS   Days to keep backups (default: 7)"
    echo "  S3_BUCKET        S3 bucket name"
    echo "  S3_PREFIX        S3 prefix/folder (default: brain-capital-backups)"
    echo "  GDRIVE_REMOTE    rclone remote name (default: gdrive)"
    echo "  GDRIVE_FOLDER    Google Drive folder (default: brain-capital-backups)"
    echo ""
    echo "Crontab example (daily at 2 AM):"
    echo "  0 2 * * * $SCRIPT_DIR/backup_db.sh >> /var/log/brain-capital-backup.log 2>&1"
}

# ==================== MAIN ====================

main() {
    log "=========================================="
    log "🚀 Brain Capital Database Backup"
    log "=========================================="
    log "Timestamp: $TIMESTAMP"
    log "Backup directory: $BACKUP_DIR"
    log ""
    
    # Parse arguments
    UPLOAD_S3=false
    UPLOAD_GDRIVE=false
    
    for arg in "$@"; do
        case $arg in
            --upload-s3)
                UPLOAD_S3=true
                ;;
            --upload-gdrive)
                UPLOAD_GDRIVE=true
                ;;
            --upload-all)
                UPLOAD_S3=true
                UPLOAD_GDRIVE=true
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                error "Unknown option: $arg"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Run backup steps
    create_backup_dir
    check_docker
    create_backup
    compress_backup
    rotate_backups
    
    # Upload to cloud storage if requested
    if [ "$UPLOAD_S3" = true ]; then
        upload_to_s3
    fi
    
    if [ "$UPLOAD_GDRIVE" = true ]; then
        upload_to_gdrive
    fi
    
    show_summary
    
    log ""
    log "✅ Backup completed successfully!"
}

main "$@"

