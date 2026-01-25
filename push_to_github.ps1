# Push Local MIMIC Code to GitHub (PowerShell)
# ============================================
#
# This script initializes git, adds all files, and pushes to GitHub
#
# USAGE:
#   .\push_to_github.ps1                    # Push to main branch
#   .\push_to_github.ps1 -Branch develop  # Push to specific branch

param(
    [string]$Branch = "main"
)

$GITHUB_REPO = "https://github.com/mimiccash-ops/MIMIC.git"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Pushing MIMIC to GitHub" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
try {
    $null = git --version
} catch {
    Write-Host "❌ Git is not installed. Please install Git for Windows first." -ForegroundColor Red
    Write-Host "Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Initialize git if not already initialized
if (-not (Test-Path .git)) {
    Write-Host "ℹ️  Initializing git repository..." -ForegroundColor Cyan
    git init
    Write-Host "✅ Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Git repository already initialized" -ForegroundColor Cyan
}

# Add remote if it doesn't exist
$remoteExists = $false
try {
    $null = git remote get-url origin 2>$null
    $remoteExists = $true
} catch {
    $remoteExists = $false
}

if (-not $remoteExists) {
    Write-Host "ℹ️  Adding GitHub remote..." -ForegroundColor Cyan
    git remote add origin $GITHUB_REPO
    Write-Host "✅ Remote added" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Remote already exists" -ForegroundColor Cyan
    git remote set-url origin $GITHUB_REPO
}

# Create .gitignore if it doesn't exist
if (-not (Test-Path .gitignore)) {
    Write-Host "ℹ️  Creating .gitignore..." -ForegroundColor Cyan
    @"
# Python
__pycache__/
*.py[cod]
*`$py.class
*.so
.Python
venv/
.venv/
env/
ENV/
*.egg-info/
dist/
build/

# Database
*.db
*.sqlite
*.sqlite3
instance/

# Environment
.env
.env.local
*.log
logs/

# Secrets
secrets/
*.key
*.pem

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Node
node_modules/
npm-debug.log

# Testing
.pytest_cache/
.coverage
htmlcov/

# Temporary
*.tmp
*.bak
*.backup
"@ | Out-File -FilePath .gitignore -Encoding UTF8
    Write-Host "✅ .gitignore created" -ForegroundColor Green
}

# Add all files
Write-Host "ℹ️  Adding files to git..." -ForegroundColor Cyan
git add .

# Check if there are changes to commit
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "⚠️  No changes to commit" -ForegroundColor Yellow
} else {
    # Commit
    Write-Host "ℹ️  Committing changes..." -ForegroundColor Cyan
    $commitMessage = "Initial commit: MIMIC v4.0"
    try {
        git commit -m $commitMessage
    } catch {
        $commitMessage = "Update: $(Get-Date -Format 'yyyy-MM-dd')"
        git commit -m $commitMessage
    }
    Write-Host "✅ Changes committed" -ForegroundColor Green
}

# Push to GitHub
Write-Host "ℹ️  Pushing to GitHub ($Branch branch)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  You may be prompted for GitHub credentials" -ForegroundColor Yellow
Write-Host ""

# Try to push, create branch if needed
try {
    git push -u origin $Branch
    Write-Host ""
    Write-Host "✅ Successfully pushed to GitHub!" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "⚠️  Push failed. Trying to create branch..." -ForegroundColor Yellow
    try {
        git branch -M $Branch 2>$null
        git push -u origin $Branch --force
        Write-Host ""
        Write-Host "✅ Successfully pushed to GitHub!" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "❌ Push failed. Possible reasons:" -ForegroundColor Red
        Write-Host "   1. Repository doesn't exist or you don't have access" -ForegroundColor Yellow
        Write-Host "   2. Authentication failed" -ForegroundColor Yellow
        Write-Host "   3. Branch protection rules" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "💡 Solutions:" -ForegroundColor Cyan
        Write-Host "   - Check repository URL: $GITHUB_REPO" -ForegroundColor Cyan
        Write-Host "   - Use SSH: git remote set-url origin git@github.com:mimiccash-ops/MIMIC.git" -ForegroundColor Cyan
        Write-Host "   - Or use GitHub CLI: gh auth login" -ForegroundColor Cyan
        Write-Host "   - Or use Personal Access Token as password" -ForegroundColor Cyan
        exit 1
    }
}

Write-Host ""
Write-Host "Repository: $GITHUB_REPO" -ForegroundColor Cyan
Write-Host "Branch: $Branch" -ForegroundColor Cyan
Write-Host ""
Write-Host "Now you can clone on your VPS:" -ForegroundColor Green
Write-Host "  git clone $GITHUB_REPO" -ForegroundColor Cyan
Write-Host ""
