# Quick deployment script for trading_engine.py fix
# Usage: .\deploy_fix.ps1

$VPS_HOST = "38.180.147.102"
$VPS_USER = "root"
$VPS_PASSWORD = "BY2YQ35j3v"
$REMOTE_PATH = "/var/www/mimic"

Write-Host "🚀 Deploying trading_engine.py fix to VPS..." -ForegroundColor Cyan

# Use SSH with password via sshpass (if available) or plink
# For Windows PowerShell, we'll use SCP/SSH commands

# Check if OpenSSH is available
if (Get-Command ssh -ErrorAction SilentlyContinue) {
    Write-Host "✅ OpenSSH found" -ForegroundColor Green
    
    # Copy file using SCP (password will be prompted or use key)
    Write-Host "📤 Uploading trading_engine.py..." -ForegroundColor Yellow
    scp -o StrictHostKeyChecking=no trading_engine.py "${VPS_USER}@${VPS_HOST}:${REMOTE_PATH}/trading_engine.py"
    
    Write-Host "🔄 Restarting worker service..." -ForegroundColor Yellow
    ssh -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" "sudo systemctl restart mimic-worker && sudo systemctl status mimic-worker --no-pager"
    
    Write-Host "📋 Checking recent logs..." -ForegroundColor Yellow
    ssh -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_HOST}" "tail -50 /var/log/arq/worker.log 2>/dev/null || journalctl -u mimic-worker -n 50 --no-pager"
    
} else {
    Write-Host "⚠️ OpenSSH not found. Please run these commands manually on the VPS:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Copy trading_engine.py to the VPS manually" -ForegroundColor Cyan
    Write-Host "2. SSH to VPS: ssh root@${VPS_HOST}" -ForegroundColor Cyan
    Write-Host "3. Run: sudo systemctl restart mimic-worker" -ForegroundColor Cyan
    Write-Host "4. Check logs: sudo journalctl -u mimic-worker -n 100 -f" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "✅ Deployment script complete!" -ForegroundColor Green
