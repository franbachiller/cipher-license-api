# Simple deployment script
$PEM_KEY = "C:\ruta\a\clave.pem"
$VPS_IP = "<IP_DEL_VPS>"
$VPS_USER = "ubuntu"
$LOCAL_DIR = $PSScriptRoot

Write-Host "============================================================"
Write-Host "CIPHER API - DEPLOYMENT"
Write-Host "============================================================"
Write-Host ""

# Test SSH
Write-Host "1. Testing SSH connection..."
ssh -i $PEM_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" "echo OK"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SSH connection failed"
    exit 1
}
Write-Host "   SSH OK"
Write-Host ""

# Create temp directory
Write-Host "2. Creating temp directory on VPS..."
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "mkdir -p /tmp/cipher-api-upload"
Write-Host "   Directory created"
Write-Host ""

# Upload files
Write-Host "3. Uploading files (this may take a few minutes)..."
scp -i $PEM_KEY -r "$LOCAL_DIR\*" "$VPS_USER@${VPS_IP}:/tmp/cipher-api-upload/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: File upload failed"
    exit 1
}
Write-Host "   Files uploaded"
Write-Host ""

# Make script executable
Write-Host "4. Preparing deployment script..."
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "chmod +x /tmp/cipher-api-upload/deploy_to_vps.sh"
Write-Host "   Script ready"
Write-Host ""

# Run deployment
Write-Host "5. Running deployment on VPS..."
Write-Host "============================================================"
ssh -i $PEM_KEY -t "$VPS_USER@$VPS_IP" "cd /tmp/cipher-api-upload && ./deploy_to_vps.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "DEPLOYMENT SUCCESSFUL!"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host "Test: curl http://$VPS_IP/health"
} else {
    Write-Host ""
    Write-Host "DEPLOYMENT FAILED - Check logs above"
}

# Cleanup
Write-Host ""
Write-Host "6. Cleaning up..."
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "rm -rf /tmp/cipher-api-upload"
Write-Host "   Done"
