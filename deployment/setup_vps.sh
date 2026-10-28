#!/bin/bash

# Cipher License System - VPS Setup Script
# This script automates the deployment of the Cipher License API on a fresh Ubuntu VPS

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Starting Cipher License System VPS Setup..."

# Step 1: Update system
log_info "Step 1/10: Updating system packages..."
apt update && apt upgrade -y
apt install -y git curl wget build-essential software-properties-common

# Step 2: Install PostgreSQL
log_info "Step 2/10: Installing PostgreSQL..."
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql

# Step 3: Install Python 3.10+
log_info "Step 3/10: Installing Python 3.10+..."
apt install -y python3 python3-pip python3-venv python3-dev libpq-dev

# Step 4: Create application directory
log_info "Step 4/10: Setting up application directory..."
APP_DIR="/opt/cipher-license/CipherAPI"
if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory not found. Please clone the repository to /opt/cipher-license first."
    exit 1
fi

cd "$APP_DIR"

# Step 5: Create Python virtual environment
log_info "Step 5/10: Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r api_server/requirements.txt

# Step 6: Configure database
log_info "Step 6/10: Configuring PostgreSQL database..."

# Generate secure password
DB_PASSWORD=$(openssl rand -base64 24)

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE cipher_license;
CREATE USER cipher_admin WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE cipher_license TO cipher_admin;
\q
EOF

# Run schema
sudo -u postgres psql -d cipher_license -f schema.sql

log_info "Database created successfully"
log_info "Database credentials:"
log_info "  User: cipher_admin"
log_info "  Password: $DB_PASSWORD"
log_info "  Database: cipher_license"

# Step 7: Generate secrets and configure environment
log_info "Step 7/10: Generating secrets and configuring environment..."

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
AES_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create .env file
cat > api_server/.env <<EOF
# Flask Configuration
SECRET_KEY=$SECRET_KEY
DEBUG=False

# Database Configuration
DATABASE_URL=postgresql://cipher_admin:$DB_PASSWORD@localhost:5432/cipher_license
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# JWT Configuration
JWT_SECRET_KEY=$JWT_SECRET
JWT_EXPIRATION_MINUTES=5

# AES Encryption Configuration
AES_ENCRYPTION_KEY=$AES_KEY

# Binary Storage
BINARY_STORAGE_PATH=/opt/cipher-license/CipherAPI/api_server/binaries

# Rate Limiting
RATE_LIMIT_AUTH=10 per minute
RATE_LIMIT_API=60 per minute

# Session Management
SESSION_CLEANUP_INTERVAL_MINUTES=5
SESSION_HEARTBEAT_TIMEOUT_SECONDS=90

# Admin Authentication
ADMIN_TOKEN=$ADMIN_TOKEN

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/cipher-api/api_server.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# Server Configuration
PORT=5000
EOF

log_info "Environment configured successfully"

# Step 8: Create log directory
log_info "Step 8/10: Creating log directory..."
mkdir -p /var/log/cipher-api
chown www-data:www-data /var/log/cipher-api

# Create binaries directory
mkdir -p api_server/binaries
chown www-data:www-data api_server/binaries

# Step 9: Install and configure systemd service
log_info "Step 9/10: Configuring systemd service..."
cp cipher-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cipher-api
systemctl start cipher-api

# Wait for service to start
sleep 3

if systemctl is-active --quiet cipher-api; then
    log_info "Cipher API service started successfully"
else
    log_error "Failed to start Cipher API service"
    log_info "Check logs with: journalctl -u cipher-api -n 50"
    exit 1
fi

# Step 10: Install and configure Nginx
log_info "Step 10/10: Installing and configuring Nginx..."
apt install -y nginx

# Prompt for domain
read -p "Enter your domain name (e.g., api.example.com) or press Enter to skip SSL setup: " DOMAIN

if [ -n "$DOMAIN" ]; then
    # Replace domain in nginx config
    sed "s/api.tu-dominio.com/$DOMAIN/g" nginx-cipher-api.conf > /etc/nginx/sites-available/cipher-api
    
    # Enable site
    ln -sf /etc/nginx/sites-available/cipher-api /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx config
    nginx -t
    
    # Restart nginx
    systemctl restart nginx
    systemctl enable nginx
    
    # Install certbot for SSL
    log_info "Installing Certbot for SSL..."
    apt install -y certbot python3-certbot-nginx
    
    # Get SSL certificate
    log_info "Obtaining SSL certificate..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
    
    log_info "SSL configured successfully for $DOMAIN"
else
    log_warn "Skipping SSL setup. You can configure it later with: sudo certbot --nginx"
fi

# Configure firewall
log_info "Configuring firewall..."
apt install -y ufw
ufw --force enable
ufw allow ssh
ufw allow 'Nginx Full'

# Create backup script
log_info "Creating backup script..."
cat > /usr/local/bin/backup-cipher-db.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/cipher"
mkdir -p $BACKUP_DIR
sudo -u postgres pg_dump cipher_license | gzip > $BACKUP_DIR/cipher_$(date +%Y%m%d_%H%M%S).sql.gz
find $BACKUP_DIR -name "cipher_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-cipher-db.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-cipher-db.sh") | crontab -

log_info "Backup script configured (runs daily at 2 AM)"

# Print summary
echo ""
echo "=========================================="
log_info "Cipher License System Setup Complete!"
echo "=========================================="
echo ""
log_info "Service Status:"
systemctl status cipher-api --no-pager -l
echo ""
log_info "Important Information:"
echo "  - Database User: cipher_admin"
echo "  - Database Password: $DB_PASSWORD"
echo "  - Admin Token: $ADMIN_TOKEN"
echo "  - Application Directory: /opt/cipher-license/CipherAPI"
echo "  - Log Directory: /var/log/cipher-api"
echo ""
log_info "Next Steps:"
echo "  1. Upload and encrypt your binaries:"
echo "     cd /opt/cipher-license/CipherAPI"
echo "     source venv/bin/activate"
echo "     python encrypt_binaries.py /path/to/loader.exe api_server/binaries/loader.bin"
echo "     python encrypt_binaries.py /path/to/driver.sys api_server/binaries/driver.bin"
echo "     python encrypt_binaries.py /path/to/cheat.dll api_server/binaries/cheat.bin"
echo ""
echo "  2. Create your first license:"
echo "     python admin.py create --expires '2025-12-31 23:59:59' --sessions 1 --note 'Test License'"
echo ""
echo "  3. Test the API:"
if [ -n "$DOMAIN" ]; then
    echo "     curl https://$DOMAIN/health"
else
    echo "     curl http://localhost:5000/health"
fi
echo ""
log_info "Useful Commands:"
echo "  - View logs: sudo journalctl -u cipher-api -f"
echo "  - Restart service: sudo systemctl restart cipher-api"
echo "  - Check status: sudo systemctl status cipher-api"
echo "  - Admin CLI: cd /opt/cipher-license/CipherAPI && source venv/bin/activate && python admin.py"
echo ""
log_warn "IMPORTANT: Save the database password and admin token in a secure location!"
echo ""
log_info "Setup completed successfully! 🚀"
