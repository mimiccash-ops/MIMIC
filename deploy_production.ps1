# =============================================================================
# BRAIN CAPITAL - PRODUCTION DEPLOYMENT (PowerShell)
# https://mimic.cash
# =============================================================================
# Run as Administrator for firewall rules
# Right-click -> Run with PowerShell
# =============================================================================

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Brain Capital - Production Server"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        BRAIN CAPITAL - PRODUCTION DEPLOYMENT                 ║" -ForegroundColor Cyan
Write-Host "║               https://mimic.cash                             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# ==================== CONFIGURATION ====================
$ProductionDomain = "https://mimic.cash,https://www.mimic.cash"
$ServerPort = 80

# ==================== CHECK PYTHON ====================
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ==================== CREATE .ENV FILE ====================
Write-Host "[2/6] Setting up environment..." -ForegroundColor Yellow

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[INFO] Generating security keys..." -ForegroundColor Cyan
    
    # Generate keys using Python
    $secretKey = python -c "import secrets; print(secrets.token_hex(32))"
    $fernetKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    
    $envContent = @"
# BRAIN CAPITAL - PRODUCTION ENVIRONMENT
# Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# Flask environment - PRODUCTION MODE
FLASK_ENV=production

# Secret key for sessions (auto-generated)
FLASK_SECRET_KEY=$secretKey

# Master encryption key (auto-generated)
BRAIN_CAPITAL_MASTER_KEY=$fernetKey

# Production domain
PRODUCTION_DOMAIN=$ProductionDomain

# Database (leave empty for SQLite)
DATABASE_URL=

# Redis (optional)
REDIS_URL=
"@
    
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "[OK] .env file created with auto-generated keys" -ForegroundColor Green
} else {
    Write-Host "[OK] .env file exists" -ForegroundColor Green
}

# ==================== LOAD ENVIRONMENT VARIABLES ====================
Write-Host "[3/6] Loading environment variables..." -ForegroundColor Yellow

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Force production settings
$env:FLASK_ENV = "production"
$env:PRODUCTION_DOMAIN = $ProductionDomain

Write-Host "[OK] FLASK_ENV = $env:FLASK_ENV" -ForegroundColor Green
Write-Host "[OK] PRODUCTION_DOMAIN = $env:PRODUCTION_DOMAIN" -ForegroundColor Green

# ==================== INSTALL DEPENDENCIES ====================
Write-Host "[4/6] Checking dependencies..." -ForegroundColor Yellow

$waitressInstalled = python -c "import waitress; print('ok')" 2>&1
if ($waitressInstalled -ne "ok") {
    Write-Host "[INFO] Installing waitress (production server)..." -ForegroundColor Cyan
    pip install waitress --quiet
}

Write-Host "[OK] Dependencies ready" -ForegroundColor Green

# ==================== FIREWALL RULES ====================
Write-Host "[5/6] Checking firewall..." -ForegroundColor Yellow

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    $ruleName = "Brain Capital Web Server"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    
    if (-not $existingRule) {
        Write-Host "[INFO] Adding firewall rule for port $ServerPort..." -ForegroundColor Cyan
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $ServerPort -Action Allow | Out-Null
        Write-Host "[OK] Firewall rule added" -ForegroundColor Green
    } else {
        Write-Host "[OK] Firewall rule exists" -ForegroundColor Green
    }
} else {
    Write-Host "[WARN] Run as Administrator to configure firewall" -ForegroundColor Yellow
}

# ==================== START SERVER ====================
Write-Host "[6/6] Starting production server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  PRODUCTION SERVER RUNNING                                   ║" -ForegroundColor Green
Write-Host "║  Local:  http://localhost (port 80)                          ║" -ForegroundColor Green
Write-Host "║  Domain: https://mimic.cash                                  ║" -ForegroundColor Green
Write-Host "║  Press Ctrl+C to stop                                        ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Start server
$pythonCode = @"
import os
os.environ['FLASK_ENV'] = 'production'
os.environ['PRODUCTION_DOMAIN'] = '$ProductionDomain'

from waitress import serve
from app import app

print('[OK] Waitress production server started')
print('[OK] Listening on http://0.0.0.0:$ServerPort')
print('')

serve(app, host='0.0.0.0', port=$ServerPort, threads=8, url_scheme='https')
"@

python -c $pythonCode

