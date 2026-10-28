# Check and Restart CipherAPI Service on VPS
# This script checks if the service is running and restarts it if needed

$PEM_KEY = "C:\ruta\a\clave.pem"
$VPS_IP = "<IP_DEL_VPS>"
$VPS_USER = "ubuntu"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CipherAPI Service Check & Restart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if service is running
Write-Host "[*] Checking service status..." -ForegroundColor Yellow
$status = ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo systemctl is-active cipher-api"

if ($status -eq "active") {
    Write-Host "[+] Service is running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "[*] Testing API endpoint..." -ForegroundColor Yellow
    
    try {
        $response = Invoke-WebRequest -Uri "http://$VPS_IP`:5000/health" -TimeoutSec 5
        Write-Host "[+] API is responding: $($response.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "[!] API not responding, restarting..." -ForegroundColor Red
        ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo systemctl restart cipher-api"
        Start-Sleep -Seconds 3
        Write-Host "[+] Service restarted!" -ForegroundColor Green
    }
} else {
    Write-Host "[!] Service is NOT running!" -ForegroundColor Red
    Write-Host "[*] Starting service..." -ForegroundColor Yellow
    
    ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo systemctl start cipher-api"
    Start-Sleep -Seconds 3
    
    $newStatus = ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo systemctl is-active cipher-api"
    
    if ($newStatus -eq "active") {
        Write-Host "[+] Service started successfully!" -ForegroundColor Green
    } else {
        Write-Host "[!] Failed to start service. Checking logs..." -ForegroundColor Red
        Write-Host ""
        ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo journalctl -u cipher-api -n 20 --no-pager"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "sudo systemctl status cipher-api --no-pager -l"

Write-Host ""
Write-Host "[*] Done!" -ForegroundColor Green
