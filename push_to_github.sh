#!/bin/bash
#
# Push Local MIMIC Code to GitHub
# ================================
#
# This script initializes git, adds all files, and pushes to GitHub
#
# USAGE:
#   ./push_to_github.sh                    # Push to main branch
#   ./push_to_github.sh --branch develop    # Push to specific branch
#

set -e

GITHUB_REPO="https://github.com/mimiccash-ops/MIMIC.git"
BRANCH="main"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --branch|-b)
            BRANCH="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--branch BRANCH_NAME]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pushing MIMIC to GitHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first."
    exit 1
fi

# Initialize git if not already initialized
if [[ ! -d .git ]]; then
    echo "ℹ️  Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
else
    echo "ℹ️  Git repository already initialized"
fi

# Add remote if it doesn't exist
if ! git remote get-url origin &> /dev/null; then
    echo "ℹ️  Adding GitHub remote..."
    git remote add origin "$GITHUB_REPO"
    echo "✅ Remote added"
else
    echo "ℹ️  Remote already exists"
    git remote set-url origin "$GITHUB_REPO"
fi

# Create .gitignore if it doesn't exist
if [[ ! -f .gitignore ]]; then
    echo "ℹ️  Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
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
EOF
    echo "✅ .gitignore created"
fi

# Add all files
echo "ℹ️  Adding files to git..."
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "⚠️  No changes to commit"
else
    # Commit
    echo "ℹ️  Committing changes..."
    git commit -m "Initial commit: MIMIC v4.0" || git commit -m "Update: $(date +%Y-%m-%d)"
    echo "✅ Changes committed"
fi

# Push to GitHub
echo "ℹ️  Pushing to GitHub ($BRANCH branch)..."
echo ""
echo "⚠️  You may be prompted for GitHub credentials"
echo ""

# Try to push, create branch if needed
git push -u origin "$BRANCH" || {
    echo ""
    echo "⚠️  Push failed. Trying to create branch..."
    git branch -M "$BRANCH" 2>/dev/null || true
    git push -u origin "$BRANCH" --force || {
        echo ""
        echo "❌ Push failed. Possible reasons:"
        echo "   1. Repository doesn't exist or you don't have access"
        echo "   2. Authentication failed"
        echo "   3. Branch protection rules"
        echo ""
        echo "💡 Solutions:"
        echo "   - Check repository URL: $GITHUB_REPO"
        echo "   - Use SSH: git remote set-url origin git@github.com:mimiccash-ops/MIMIC.git"
        echo "   - Or use GitHub CLI: gh auth login"
        exit 1
    }
}

echo ""
echo "✅ Successfully pushed to GitHub!"
echo ""
echo "Repository: $GITHUB_REPO"
echo "Branch: $BRANCH"
echo ""
echo "Now you can clone on your VPS:"
echo "  git clone $GITHUB_REPO"
echo ""
