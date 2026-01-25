#!/bin/bash
# Quick fix for git conflict and missing tailwind.input.css
# Run this on the server: bash quick_fix.sh

set -e

cd /var/www/mimic

echo "Step 1: Stashing local changes..."
git stash push -m "Stash before pull" fix_frontend_design.sh || true

echo "Step 2: Pulling latest changes..."
git pull

echo "Step 3: Creating tailwind.input.css..."
mkdir -p /var/www/mimic/static/css
cat > /var/www/mimic/static/css/tailwind.input.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles can be added here */
EOF

echo "Step 4: Verifying file exists..."
if [[ -f /var/www/mimic/static/css/tailwind.input.css ]]; then
    echo "✅ tailwind.input.css created successfully"
else
    echo "❌ Failed to create tailwind.input.css"
    exit 1
fi

echo "Step 5: Rebuilding CSS..."
cd /var/www/mimic
npm run build

echo "Step 6: Restarting services..."
sudo systemctl reload nginx
sudo systemctl restart mimic

echo "✅ All done! Check https://mimiccash.com"
