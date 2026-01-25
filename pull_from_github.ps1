# Pull Updates from GitHub (PowerShell)
# =====================================
#
# This script pulls the latest changes from GitHub
#
# USAGE:
#   .\pull_from_github.ps1

param(
    [switch]$NoStash = $false
)

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Pulling Updates from GitHub" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
try {
    $null = git --version
} catch {
    Write-Host "❌ Git is not installed." -ForegroundColor Red
    exit 1
}

# Check if in git repository
if (-not (Test-Path .git)) {
    Write-Host "❌ Not a git repository!" -ForegroundColor Red
    exit 1
}

# Check for local changes
$status = git status --porcelain
if (-not [string]::IsNullOrWhiteSpace($status) -and -not $NoStash) {
    Write-Host "⚠️  Local changes detected. Stashing..." -ForegroundColor Yellow
    git stash
    $stashed = $true
} else {
    $stashed = $false
}

# Fetch updates
Write-Host "ℹ️  Fetching updates from GitHub..." -ForegroundColor Cyan
git fetch origin

# Check if there are updates
$local = git rev-parse @
$remote = git rev-parse @{u}

if ($local -eq $remote) {
    Write-Host "✅ Already up to date!" -ForegroundColor Green
    if ($stashed) {
        git stash pop
    }
} else {
    Write-Host "ℹ️  Pulling changes..." -ForegroundColor Cyan
    git pull origin main
    
    if ($stashed) {
        Write-Host "ℹ️  Restoring local changes..." -ForegroundColor Cyan
        git stash pop
    }
    
    Write-Host "✅ Updated successfully!" -ForegroundColor Green
}

Write-Host ""
