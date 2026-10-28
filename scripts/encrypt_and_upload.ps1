# Encrypt and Upload Binaries to VPS
# This script encrypts the three required binaries and uploads them to the VPS

$ErrorActionPreference = "Stop"

# Configuration
$PEM_KEY = "C:\ruta\a\clave.pem"
$VPS_IP = "<IP_DEL_VPS>"
$VPS_USER = "ubuntu"
$VPS_BINARIES_DIR = "/opt/cipher-api/api_server/binaries"

# Load AES key from .env
$AES_KEY = (Get-Content "api_server\.env" | Select-String "AES_ENCRYPTION_KEY").ToString().Split('=')[1].Trim()
$env:AES_ENCRYPTION_KEY = $AES_KEY

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Encrypt and Upload Binaries" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Binary paths
$GDRV_LOADER = "..\GDRVLoader\x64\Release\GDRVLoader.exe"
$DRIVER_SYS = "..\vac-bypass-kernel\src\bin\Release\driver.sys"
$CIPHER_EXE = "..\Cipher\build\x64\Release\Cipher.exe"

Write-Host "[*] Checking for required binaries..." -ForegroundColor Yellow

# Check if GDRVLoader.exe exists
if (!(Test-Path $GDRV_LOADER)) {
    Write-Host "[!] GDRVLoader.exe not found at: $GDRV_LOADER" -ForegroundColor Red
    Write-Host "[*] Searching for alternative location..." -ForegroundColor Yellow
    $GDRV_LOADER = Get-ChildItem -Path "GDRVLoader" -Filter "GDRVLoader.exe" -Recurse | Select-Object -First 1 -ExpandProperty FullName
    if (!$GDRV_LOADER) {
        Write-Host "[!] GDRVLoader.exe not found anywhere!" -ForegroundColor Red
        exit 1
    }
}

# Check if driver.sys exists
if (!(Test-Path $DRIVER_SYS)) {
    Write-Host "[!] driver.sys not found at: $DRIVER_SYS" -ForegroundColor Red
    exit 1
}

# Check if Cipher.exe exists
if (!(Test-Path $CIPHER_EXE)) {
    Write-Host "[!] Cipher.exe not found at: $CIPHER_EXE" -ForegroundColor Red
    Write-Host "[*] Please compile the Cipher cheat first" -ForegroundColor Yellow
    exit 1
}

Write-Host "[+] Found GDRVLoader.exe" -ForegroundColor Green
Write-Host "[+] Found driver.sys" -ForegroundColor Green
Write-Host "[+] Found Cipher.exe" -ForegroundColor Green

# Create temp directory
$TEMP_DIR = "CipherAPI\api_server\binaries\temp"
New-Item -ItemType Directory -Force -Path $TEMP_DIR | Out-Null

Write-Host ""
Write-Host "[*] Copying production binaries..." -ForegroundColor Yellow

# Copy real binaries
Copy-Item $GDRV_LOADER "$TEMP_DIR\loader_plain.exe" -Force
Copy-Item $DRIVER_SYS "$TEMP_DIR\driver_plain.sys" -Force
Copy-Item $CIPHER_EXE "$TEMP_DIR\cheat_plain.exe" -Force

Write-Host "[+] Production binaries prepared" -ForegroundColor Green

# Encrypt binaries
Write-Host ""
Write-Host "[*] Encrypting binaries with AES-256-CBC..." -ForegroundColor Yellow

python scripts\encrypt_binaries.py --batch --output-dir api_server\binaries `
    api_server\binaries\temp\loader_plain.exe `
    api_server\binaries\temp\driver_plain.sys `
    api_server\binaries\temp\cheat_plain.exe

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Encryption failed!" -ForegroundColor Red
    exit 1
}

cd ..

# Rename encrypted files
Move-Item "CipherAPI\api_server\binaries\loader_plain.enc" "CipherAPI\api_server\binaries\loader.enc" -Force
Move-Item "CipherAPI\api_server\binaries\driver_plain.enc" "CipherAPI\api_server\binaries\driver.enc" -Force
Move-Item "CipherAPI\api_server\binaries\cheat_plain.enc" "CipherAPI\api_server\binaries\cheat.enc" -Force

Write-Host ""
Write-Host "[+] Binaries encrypted successfully!" -ForegroundColor Green

# Clean up temp files
Remove-Item -Recurse -Force "$TEMP_DIR"

# Upload to VPS
Write-Host ""
Write-Host "[*] Uploading encrypted binaries to VPS..." -ForegroundColor Yellow

scp -i $PEM_KEY `
    CipherAPI\api_server\binaries\loader.enc `
    CipherAPI\api_server\binaries\driver.enc `
    CipherAPI\api_server\binaries\cheat.enc `
    "$VPS_USER@$VPS_IP`:$VPS_BINARIES_DIR/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Upload failed!" -ForegroundColor Red
    exit 1
}

Write-Host "[+] Binaries uploaded successfully!" -ForegroundColor Green

# Verify on VPS
Write-Host ""
Write-Host "[*] Verifying files on VPS..." -ForegroundColor Yellow
ssh -i $PEM_KEY "$VPS_USER@$VPS_IP" "ls -lh $VPS_BINARIES_DIR/*.enc"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Encrypted binaries are now available on the VPS." -ForegroundColor Green
Write-Host "You can now test the CipherLoader." -ForegroundColor Green
