#!/bin/bash
#
# Automated Deployment Script for Cipher API
# VPS: <IP_DEL_VPS> (AWS EC2)
#
# Usage:
#   1. Upload this script and your code to the VPS
#   2. Run: chmod +x deploy_to_vps.sh
#   3. Run: ./deploy_to_vps.sh
#

set -e  # Exit on error

echo "============================================================"
echo "CIPHER API - AUTOMATED DEPLOYMENT"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run as root. Run as ubuntu user."
    exit 1
fi

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="/opt/cipher-api"

print_info "Script directory: $SCRIPT_DIR"
print_info "Target directory: $APP_DIR"

# Step 1: Update system
print_info "Step 1: Updating system packages..."
sudo apt update -qq
sudo apt upgrade -y -qq
print_success "System updated"

# Step 2: Install dependencies
print_info "Step 2: Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx -qq
print_success "Dependencies installed"

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_info "Python version: $PYTHON_VERSION"

# Step 3: Create application directory
print_info "Step 3: Setting up application directory..."
if [ ! -d "$APP_DIR" ]; then
    sudo mkdir -p "$APP_DIR"
    sudo chown $USER:$USER "$APP_DIR"
    print_success "Created $APP_DIR"
else
    print_info "Directory $APP_DIR already exists"
fi

# Step 4: Copy files
print_info "Step 4: Copying application files..."
if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    # Copy all files from current directory to app directory
    cp -r "$SCRIPT_DIR"/* "$APP_DIR/" 2>/dev/null || true
    print_success "Files copied to $APP_DIR"
else
    print_info "Already in target directory"
fi

cd "$APP_DIR"

# Step 5: Create virtual environment
print_info "Step 5: Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Step 6: Install Python dependencies
print_info "Step 6: Installing Python packages..."
pip install --upgrade pip -q
pip install -r api_server/requirements.txt -q
pip install gunicorn -q
print_success "Python packages installed"

# Step 7: Check .env file
print_info "Step 7: Checking configuration..."
if [ ! -f "api_server/.env" ]; then
    print_error ".env file not found!"
    print_info "Please create api_server/.env with your configuration"
    print_info "See VPS_DEPLOYMENT_GUIDE.md for details"
    exit 1
else
    print_success ".env file found"
    
    # Verify critical variables
    if grep -q "DATABASE_URL=postgresql" api_server/.env; then
        print_success "DATABASE_URL configured"
    else
        print_error "DATABASE_URL not configured in .env"
        exit 1
    fi
fi

# Step 8: Create binaries directory
print_info "Step 8: Setting up binaries directory..."
mkdir -p api_server/binaries
print_success "Binaries directory ready"

# Check if binaries exist
BINARY_COUNT=$(ls -1 api_server/binaries/*.bin 2>/dev/null | wc -l)
if [ "$BINARY_COUNT" -gt 0 ]; then
    print_success "Found $BINARY_COUNT binary file(s)"
else
    print_info "No binary files found in api_server/binaries/"
    print_info "Upload your encrypted binaries (loader.bin, driver.bin, cheat.bin)"
fi

# Step 9: Test API locally
print_info "Step 9: Testing API..."
timeout 5 python api_server/app.py &
API_PID=$!
sleep 3

if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    print_success "API health check passed"
    kill $API_PID 2>/dev/null || true
else
    print_error "API health check failed"
    kill $API_PID 2>/dev/null || true
    print_info "Check logs: tail -f api_server.log"
    exit 1
fi

# Step 10: Create systemd service
print_info "Step 10: Creating systemd service..."
sudo tee /etc/systemd/system/cipher-api.service > /dev/null <<EOF
[Unit]
Description=Cipher API - VPS Streaming License System
After=network.target

[Service]
Type=notify
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn \\
    --bind 127.0.0.1:5000 \\
    --workers 4 \\
    --timeout 120 \\
    --access-logfile $APP_DIR/access.log \\
    --error-logfile $APP_DIR/error.log \\
    --chdir $APP_DIR \\
    api_server.app:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service created"

# Step 11: Enable and start service
print_info "Step 11: Starting Cipher API service..."
sudo systemctl daemon-reload
sudo systemctl enable cipher-api
sudo systemctl restart cipher-api

sleep 3

if sudo systemctl is-active --quiet cipher-api; then
    print_success "Cipher API service is running"
else
    print_error "Failed to start Cipher API service"
    print_info "Check logs: sudo journalctl -u cipher-api -n 50"
    exit 1
fi

# Step 12: Configure Nginx
print_info "Step 12: Configuring Nginx..."
sudo tee /etc/nginx/sites-available/cipher-api > /dev/null <<'EOF'
server {
    listen 80;
    server_name <IP_DEL_VPS>;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=60r/m;

    # Logs
    access_log /var/log/nginx/cipher-api-access.log;
    error_log /var/log/nginx/cipher-api-error.log;

    # Health check endpoint (no rate limit)
    location /health {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Auth endpoint (strict rate limit)
    location /api/auth {
        limit_req zone=auth_limit burst=5 nodelay;
        
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Other API endpoints (normal rate limit)
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Admin endpoints (localhost only)
    location /admin/ {
        allow 127.0.0.1;
        deny all;
        
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/cipher-api /etc/nginx/sites-enabled/

# Test Nginx configuration
if sudo nginx -t 2>&1 | grep -q "successful"; then
    print_success "Nginx configuration valid"
    sudo systemctl reload nginx
    print_success "Nginx reloaded"
else
    print_error "Nginx configuration invalid"
    sudo nginx -t
    exit 1
fi

# Step 13: Configure firewall
print_info "Step 13: Configuring firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 22/tcp -q
    sudo ufw allow 80/tcp -q
    sudo ufw allow 443/tcp -q
    
    # Enable firewall if not already enabled
    echo "y" | sudo ufw enable 2>/dev/null || true
    
    print_success "Firewall configured"
else
    print_info "UFW not installed, skipping firewall configuration"
fi

# Step 14: Final verification
print_info "Step 14: Running final verification..."

# Check if API responds
sleep 2
if curl -s http://localhost/health | grep -q "healthy"; then
    print_success "API health check passed (via Nginx)"
else
    print_error "API health check failed (via Nginx)"
fi

# Check service status
if sudo systemctl is-active --quiet cipher-api; then
    print_success "Cipher API service: RUNNING"
else
    print_error "Cipher API service: NOT RUNNING"
fi

if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx service: RUNNING"
else
    print_error "Nginx service: NOT RUNNING"
fi

echo ""
echo "============================================================"
echo "✓ DEPLOYMENT COMPLETE!"
echo "============================================================"
echo ""
echo "Your API is now running at:"
echo "  • Health: http://<IP_DEL_VPS>/health"
echo "  • Auth:   http://<IP_DEL_VPS>/api/auth"
echo ""
echo "Next steps:"
echo "  1. Create a test license:"
echo "     cd $APP_DIR"
echo "     source venv/bin/activate"
echo "     python admin.py create --expires '2025-12-31' --sessions 1"
echo ""
echo "  2. Test authentication from your local machine:"
echo "     curl -X POST http://<IP_DEL_VPS>/api/auth \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"license_key\":\"YOUR_KEY\"}'"
echo ""
echo "  3. View logs:"
echo "     sudo journalctl -u cipher-api -f"
echo "     tail -f $APP_DIR/api_server.log"
echo ""
echo "  4. Manage service:"
echo "     sudo systemctl status cipher-api"
echo "     sudo systemctl restart cipher-api"
echo ""
echo "============================================================"
