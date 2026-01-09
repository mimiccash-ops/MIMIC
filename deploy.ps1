#!/usr/bin/env pwsh
<#
.SYNOPSIS
    MIMIC - One-Command VPS Deployment Script
    
.DESCRIPTION
    Uploads and syncs project files to a Linux VPS automatically.
    Uses rsync over SSH for efficient incremental transfers.
    
.USAGE
    # First time: Edit the configuration below, then run:
    .\deploy.ps1
    
    # Or with parameters:
    .\deploy.ps1 -Server "user@your-vps-ip" -Path "/var/www/mimic"
    
    # Deploy and restart service:
    .\deploy.ps1 -Restart
    
    # Dry run (show what would be transferred):
    .\deploy.ps1 -DryRun

.NOTES
    Author: MIMIC Deployment
    Requires: SSH key authentication configured, rsync on VPS
#>

param(
    [string]$Server = "",      # e.g., "root@38.180.143.20"
    [string]$Path = "",        # e.g., "/var/www/mimic"
    [string]$SSHKey = "",      # e.g., "~/.ssh/id_rsa"
    [switch]$Restart,          # Restart service after deploy
    [switch]$DryRun,           # Show what would be transferred
    [switch]$Help
)

# ============================================================================
# CONFIGURATION - Edit these values for your VPS
# ============================================================================

$CONFIG = @{
    # VPS Connection (SSH)
    VPS_USER = "root"                          # SSH username
    VPS_HOST = "38.180.147.102"                   # VPS IP or hostname (e.g., 38.180.143.20)
    VPS_PORT = "22"                            # SSH port (default: 22)
    
    # Paths
    REMOTE_PATH = "/var/www/mimic"             # Where to deploy on VPS
    SSH_KEY = ""                               # Path to SSH key (leave empty for default)
    
    # Service (for restart)
    SERVICE_NAME = "mimic"                     # systemd service name
    
    # Files to exclude from sync
    EXCLUDES = @(
        ".git"
        ".gitignore"
        ".env"
        "*.db"
        "__pycache__"
        "*.pyc"
        ".pytest_cache"
        "venv"
        ".venv"
        "node_modules"
        "*.log"
        "logs/"
        "secrets/"
        ".idea"
        ".vscode"
        "*.tmp"
        "*.bak"
        "deploy.ps1"
        "deploy.bat"
        "deploy.sh"
        "static/avatars/*"
        "!static/avatars/.gitkeep"
    )
}

# ============================================================================
# SCRIPT LOGIC - No need to edit below
# ============================================================================

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "❌ $msg" -ForegroundColor Red }

# Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           MIMIC - VPS Deployment Script                      ║" -ForegroundColor Cyan
Write-Host "║                  https://mimic.cash                          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if ($Help) {
    Write-Host @"
USAGE:
    .\deploy.ps1                    # Deploy using config settings
    .\deploy.ps1 -Restart           # Deploy and restart service
    .\deploy.ps1 -DryRun            # Preview changes without deploying
    .\deploy.ps1 -Server user@ip    # Override server
    .\deploy.ps1 -Path /var/www/app # Override remote path

FIRST TIME SETUP:
    1. Edit the CONFIG section at the top of this script
    2. Set VPS_HOST to your VPS IP address
    3. Ensure SSH key authentication is configured
    4. Run: .\deploy.ps1

"@
    exit 0
}

# Override config with parameters
if ($Server) {
    if ($Server -match "^(.+)@(.+)$") {
        $CONFIG.VPS_USER = $Matches[1]
        $CONFIG.VPS_HOST = $Matches[2]
    } else {
        $CONFIG.VPS_HOST = $Server
    }
}
if ($Path) { $CONFIG.REMOTE_PATH = $Path }
if ($SSHKey) { $CONFIG.SSH_KEY = $SSHKey }

# Validate configuration
if ($CONFIG.VPS_HOST -eq "YOUR_VPS_IP" -or [string]::IsNullOrEmpty($CONFIG.VPS_HOST)) {
    Write-Err "VPS_HOST not configured!"
    Write-Host ""
    Write-Host "Please edit deploy.ps1 and set your VPS details in the CONFIG section:" -ForegroundColor Yellow
    Write-Host '    VPS_HOST = "your-vps-ip-address"' -ForegroundColor White
    Write-Host ""
    exit 1
}

# Build SSH connection string
$SSH_TARGET = "$($CONFIG.VPS_USER)@$($CONFIG.VPS_HOST)"
$SSH_OPTS = @("-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-p", $CONFIG.VPS_PORT)
if ($CONFIG.SSH_KEY) {
    $SSH_OPTS += @("-i", $CONFIG.SSH_KEY)
}

Write-Info "Target: $SSH_TARGET`:$($CONFIG.REMOTE_PATH)"

# Check for rsync (try WSL, Git Bash, or native)
$RSYNC_CMD = $null
$USE_WSL = $false

# Try native rsync first (Git for Windows includes it)
$gitBashRsync = "C:\Program Files\Git\usr\bin\rsync.exe"
if (Test-Path $gitBashRsync) {
    $RSYNC_CMD = $gitBashRsync
    Write-Info "Using rsync from Git for Windows"
}

# Try WSL
if (-not $RSYNC_CMD) {
    try {
        $wslCheck = wsl --list 2>$null
        if ($LASTEXITCODE -eq 0) {
            $RSYNC_CMD = "wsl"
            $USE_WSL = $true
            Write-Info "Using rsync via WSL"
        }
    } catch {}
}

# If no rsync, fall back to scp
if (-not $RSYNC_CMD) {
    Write-Warn "rsync not found, using scp (slower, full transfer)"
    
    # Create exclude list for robocopy (local staging)
    $stagingDir = Join-Path $env:TEMP "mimic_deploy_$(Get-Random)"
    New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
    
    # Copy files excluding patterns
    $excludeDirs = $CONFIG.EXCLUDES | Where-Object { -not $_.Contains("*") -and -not $_.Contains("!") }
    $robocopyExcludes = $excludeDirs -join " "
    
    Write-Info "Preparing files for transfer..."
    $source = (Get-Location).Path
    robocopy $source $stagingDir /E /XD $excludeDirs /XF *.pyc *.log *.db *.tmp /NFL /NDL /NJH /NJS | Out-Null
    
    # Use scp to transfer
    Write-Info "Uploading via scp..."
    $scpArgs = @("-r", "-P", $CONFIG.VPS_PORT)
    if ($CONFIG.SSH_KEY) { $scpArgs += @("-i", $CONFIG.SSH_KEY) }
    $scpArgs += @("$stagingDir/*", "${SSH_TARGET}:$($CONFIG.REMOTE_PATH)/")
    
    if ($DryRun) {
        Write-Warn "[DRY RUN] Would execute: scp $($scpArgs -join ' ')"
    } else {
        & scp @scpArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Err "scp failed!"
            Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
            exit 1
        }
    }
    
    Remove-Item -Recurse -Force $stagingDir -ErrorAction SilentlyContinue
    Write-Success "Files uploaded via scp"
    
} else {
    # Build rsync command
    $excludeArgs = $CONFIG.EXCLUDES | ForEach-Object { "--exclude=$_" }
    
    $rsyncArgs = @(
        "-avz"                              # Archive, verbose, compress
        "--progress"                        # Show progress
        "--delete"                          # Delete files not in source
        "-e", "ssh $($SSH_OPTS -join ' ')"  # SSH options
    ) + $excludeArgs
    
    if ($DryRun) {
        $rsyncArgs += "--dry-run"
    }
    
    # Source and destination
    $source = (Get-Location).Path
    if ($USE_WSL) {
        # Convert Windows path to WSL path
        $wslSource = $source -replace "\\", "/" -replace "^([A-Za-z]):", '/mnt/$1'.ToLower()
        $rsyncArgs += @("$wslSource/", "${SSH_TARGET}:$($CONFIG.REMOTE_PATH)/")
        
        Write-Info "Syncing files..."
        $rsyncCmd = "rsync $($rsyncArgs -join ' ')"
        wsl bash -c $rsyncCmd
    } else {
        # Use native rsync (Git Bash)
        $rsyncArgs += @("./", "${SSH_TARGET}:$($CONFIG.REMOTE_PATH)/")
        
        Write-Info "Syncing files..."
        & $RSYNC_CMD @rsyncArgs
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Err "rsync failed!"
        exit 1
    }
    
    if ($DryRun) {
        Write-Warn "[DRY RUN] No files were transferred"
    } else {
        Write-Success "Files synchronized"
    }
}

# Restart service if requested
if ($Restart -and -not $DryRun) {
    Write-Info "Restarting service: $($CONFIG.SERVICE_NAME)..."
    
    $restartCmd = "sudo systemctl restart $($CONFIG.SERVICE_NAME) && sudo systemctl status $($CONFIG.SERVICE_NAME) --no-pager"
    
    $sshArgs = $SSH_OPTS + @($SSH_TARGET, $restartCmd)
    & ssh @sshArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Service restarted"
    } else {
        Write-Warn "Service restart may have issues, check logs"
    }
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
if ($DryRun) {
    Write-Host "  DRY RUN COMPLETE - No changes made" -ForegroundColor Yellow
} else {
    Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
}
Write-Host "  Target: $SSH_TARGET`:$($CONFIG.REMOTE_PATH)" -ForegroundColor White
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
