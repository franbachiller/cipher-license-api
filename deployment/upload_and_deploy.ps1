# PowerShell Script para subir código al VPS y ejecutar deployment
# 
# Uso:
#   1. Asegúrate de tener tu .pem key de AWS
#   2. Edita las variables abajo con tus valores
#   3. Ejecuta: .\upload_and_deploy.ps1
#

# ============================================================
# CONFIGURACIÓN - EDITA ESTOS VALORES
# ============================================================

# Ruta a tu archivo .pem de AWS EC2
# Busca tu archivo .pem en Downloads o donde lo guardaste cuando creaste la instancia EC2
# Ejemplo: "C:\ruta\a\clave.pem"
$PEM_KEY = "C:\ruta\a\clave.pem"

# IP de tu VPS
$VPS_IP = "<IP_DEL_VPS>"

# Usuario del VPS (normalmente 'ubuntu' para Ubuntu, 'ec2-user' para Amazon Linux)
$VPS_USER = "ubuntu"

# Directorio local de tu proyecto (donde está este script)
$LOCAL_DIR = $PSScriptRoot

# ============================================================
# NO EDITES DEBAJO DE ESTA LÍNEA
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "CIPHER API - UPLOAD AND DEPLOY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que existe la key
if (-not (Test-Path $PEM_KEY)) {
    Write-Host "✗ Error: PEM key not found at: $PEM_KEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please edit this script and set the correct path to your .pem file" -ForegroundColor Yellow
    Write-Host "You can find it in your AWS EC2 console under 'Key Pairs'" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ PEM key found" -ForegroundColor Green

# Verificar que existe .env
$ENV_FILE = Join-Path $LOCAL_DIR "api_server\.env"
if (-not (Test-Path $ENV_FILE)) {
    Write-Host "✗ Error: .env file not found at: $ENV_FILE" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create api_server\.env with your configuration" -ForegroundColor Yellow
    Write-Host "See VPS_DEPLOYMENT_GUIDE.md for details" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ .env file found" -ForegroundColor Green

# Test SSH connection
Write-Host ""
Write-Host "Testing SSH connection to $VPS_IP..." -ForegroundColor Yellow

$SSH_TEST = ssh -i $PEM_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" "echo 'Connection successful'" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ SSH connection successful" -ForegroundColor Green
} else {
    Write-Host "✗ SSH connection failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $SSH_TEST" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Check that your EC2 instance is running" -ForegroundColor Yellow
    Write-Host "2. Check that Security Group allows SSH (port 22) from your IP" -ForegroundColor Yellow
    Write-Host "3. Verify the PEM key path is correct" -ForegroundColor Yellow
    Write-Host "4. Verify the VPS_USER is correct (ubuntu or ec2-user)" -ForegroundColor Yellow
    exit 1
}

# Create temporary directory on VPS
Write-Host ""
Write-Host "Creating temporary directory on VPS..." -ForegroundColor Yellow
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "mkdir -p /tmp/cipher-api-upload"
Write-Host "✓ Temporary directory created" -ForegroundColor Green

# Upload files using SCP
Write-Host ""
Write-Host "Uploading files to VPS (this may take a few minutes)..." -ForegroundColor Yellow

# Create list of files to upload (exclude unnecessary files)
$EXCLUDE_PATTERNS = @(
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    "*.log",
    ".env.example",
    "*.md",
    "*.ps1",
    "tests"
)

# Use rsync if available, otherwise use scp
$RSYNC_AVAILABLE = Get-Command rsync -ErrorAction SilentlyContinue

if ($RSYNC_AVAILABLE) {
    Write-Host "Using rsync for faster upload..." -ForegroundColor Cyan
    
    $EXCLUDE_ARGS = $EXCLUDE_PATTERNS | ForEach-Object { "--exclude=$_" }
    
    rsync -avz --progress `
        -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" `
        $EXCLUDE_ARGS `
        "$LOCAL_DIR/" `
        "$VPS_USER@${VPS_IP}:/tmp/cipher-api-upload/"
} else {
    Write-Host "Using scp for upload..." -ForegroundColor Cyan
    
    # Upload entire directory
    scp -i $PEM_KEY -r "$LOCAL_DIR\*" "$VPS_USER@${VPS_IP}:/tmp/cipher-api-upload/"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Files uploaded successfully" -ForegroundColor Green
} else {
    Write-Host "✗ File upload failed" -ForegroundColor Red
    exit 1
}

# Make deployment script executable
Write-Host ""
Write-Host "Preparing deployment script..." -ForegroundColor Yellow
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "chmod +x /tmp/cipher-api-upload/deploy_to_vps.sh"
Write-Host "✓ Deployment script ready" -ForegroundColor Green

# Run deployment script
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RUNNING DEPLOYMENT ON VPS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

ssh -i $PEM_KEY -t "$VPS_USER@$VPS_IP" "cd /tmp/cipher-api-upload && ./deploy_to_vps.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✓ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your API is now running at:" -ForegroundColor Cyan
    Write-Host "  • Health: http://$VPS_IP/health" -ForegroundColor White
    Write-Host "  • Auth:   http://$VPS_IP/api/auth" -ForegroundColor White
    Write-Host ""
    Write-Host "Test it now:" -ForegroundColor Yellow
    Write-Host "  curl http://$VPS_IP/health" -ForegroundColor White
    Write-Host ""
    Write-Host "Create a license:" -ForegroundColor Yellow
    Write-Host "  ssh -i $PEM_KEY $VPS_USER@$VPS_IP" -ForegroundColor White
    Write-Host "  cd /opt/cipher-api" -ForegroundColor White
    Write-Host "  source venv/bin/activate" -ForegroundColor White
    Write-Host "  python admin.py create --expires '2025-12-31' --sessions 1" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "✗ DEPLOYMENT FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To debug, connect to your VPS:" -ForegroundColor Yellow
    Write-Host "  ssh -i $PEM_KEY $VPS_USER@$VPS_IP" -ForegroundColor White
    Write-Host ""
    Write-Host "Then check logs:" -ForegroundColor Yellow
    Write-Host "  sudo journalctl -u cipher-api -n 50" -ForegroundColor White
    Write-Host "  tail -f /opt/cipher-api/api_server.log" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Cleanup
Write-Host "Cleaning up temporary files..." -ForegroundColor Yellow
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "rm -rf /tmp/cipher-api-upload"
Write-Host "✓ Cleanup complete" -ForegroundColor Green
Write-Host ""
