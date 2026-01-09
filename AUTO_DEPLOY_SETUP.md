# 🚀 MIMIC Auto-Deploy Setup Guide

## Overview

This guide explains how to set up **automatic deployment** so that when you commit code from Cursor (or any Git client), your Linux VPS will automatically pull the changes and restart the site.

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Cursor     │ ───► │   GitHub     │ ───► │  Linux VPS   │
│  (Commit)    │      │  (Actions)   │      │  (Auto-Restart)│
└──────────────┘      └──────────────┘      └──────────────┘
```

---

## ⚡ Quick Setup (5 minutes)

### Step 1: Generate SSH Key for Deployment

On your **local machine** (Windows), open PowerShell:

```powershell
# Generate a new SSH key specifically for deployment
ssh-keygen -t ed25519 -C "mimic-deploy" -f "$env:USERPROFILE\.ssh\mimic_deploy_key"

# Display the PRIVATE key (you'll need this for GitHub)
Get-Content "$env:USERPROFILE\.ssh\mimic_deploy_key"

# Display the PUBLIC key (you'll need this for your VPS)
Get-Content "$env:USERPROFILE\.ssh\mimic_deploy_key.pub"
```

### Step 2: Add Public Key to Your VPS

SSH into your VPS and add the public key:

```bash
# On your VPS (as root or your deploy user)
echo "PASTE_YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these 4 secrets:

| Secret Name    | Value                                           |
|----------------|------------------------------------------------|
| `VPS_HOST`     | Your VPS IP address (e.g., `123.45.67.89`)     |
| `VPS_USER`     | SSH username (usually `root`)                   |
| `VPS_SSH_KEY`  | Entire content of your **private** key file    |
| `VPS_PORT`     | SSH port (usually `22`)                         |

> ⚠️ **Important**: For `VPS_SSH_KEY`, paste the ENTIRE private key including:
> ```
> -----BEGIN OPENSSH PRIVATE KEY-----
> ... (all the content) ...
> -----END OPENSSH PRIVATE KEY-----
> ```

### Step 4: Commit and Push!

Now when you commit and push to `main` or `master` branch:

1. In Cursor, make your changes
2. Click the Source Control icon (or Ctrl+Shift+G)
3. Stage your changes, write a commit message
4. Click ✓ Commit, then Push
5. **GitHub Actions automatically deploys to your VPS!**

You can watch the deployment progress at:
`https://github.com/YOUR_USERNAME/YOUR_REPO/actions`

---

## 🔧 VPS Initial Setup (One-Time)

If you haven't set up your VPS yet, run these commands:

```bash
# Connect to your VPS
ssh root@YOUR_VPS_IP

# Clone your repository
sudo mkdir -p /var/www
cd /var/www
sudo git clone https://github.com/YOUR_USERNAME/MIMIC.git mimic
cd mimic

# Run the installation script
chmod +x mimic-control.sh
sudo ./mimic-control.sh install

# Edit your configuration
nano .env          # Add your environment variables
nano config.ini    # Add your Binance API keys

# Start all services
sudo ./mimic-control.sh start
```

---

## 📋 What Happens During Deployment

When you push to GitHub, the following happens automatically:

1. **GitHub Actions** receives the push event
2. **SSH connection** is established to your VPS
3. **Git pull** fetches the latest code
4. **Dependencies** are updated (pip install)
5. **Database migrations** are run (if any)
6. **Services restart** (systemctl restart mimic)
7. **Health check** verifies the app is running

---

## 🛠️ Manual Commands on VPS

You can also manually control your VPS deployment:

```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Navigate to project
cd /var/www/mimic

# Manual update (same as auto-deploy)
sudo ./mimic-control.sh update

# View status
sudo ./mimic-control.sh status

# View logs
sudo ./mimic-control.sh logs

# Restart services
sudo ./mimic-control.sh restart
```

---

## ⚙️ Customization

### Change Deployment Branch

Edit `.github/workflows/deploy.yml` and modify:

```yaml
on:
  push:
    branches:
      - main        # Change this
      - production  # Or add more branches
```

### Change VPS Project Path

If your project is not at `/var/www/mimic`, edit the `APP_DIR` in:
- `.github/workflows/deploy.yml`
- `mimic-control.sh`

### Run Custom Commands After Deploy

Add to the deploy script in `.github/workflows/deploy.yml`:

```yaml
echo "Running custom post-deploy tasks..."
python your_custom_script.py
```

---

## 🔍 Troubleshooting

### Deployment Failed: Permission Denied

```bash
# On VPS, check SSH permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Verify key is added
cat ~/.ssh/authorized_keys
```

### Deployment Failed: Host Key Verification

```bash
# Add VPS to known hosts manually
ssh-keyscan -H YOUR_VPS_IP >> ~/.ssh/known_hosts
```

### Service Won't Start After Deploy

```bash
# Check logs on VPS
sudo journalctl -u mimic -n 50

# Check if port is in use
sudo lsof -i :5000

# Restart manually
sudo systemctl restart mimic
```

### Check GitHub Actions Logs

1. Go to your repo on GitHub
2. Click **Actions** tab
3. Click on the failed workflow run
4. Expand each step to see detailed logs

---

## 🔐 Security Best Practices

1. **Use a dedicated deploy key** - Don't use your personal SSH key
2. **Restrict key permissions** - The deploy key should only have access to pull code
3. **Use GitHub Environments** - Add protection rules for production deployments
4. **Keep secrets secure** - Never commit secrets to the repository

---

## 📱 Optional: Telegram Notifications

Add deployment notifications to Telegram by adding this step to `.github/workflows/deploy.yml`:

```yaml
- name: 📱 Telegram Notification
  if: always()
  run: |
    STATUS="${{ job.status }}"
    if [ "$STATUS" = "success" ]; then
      EMOJI="✅"
    else
      EMOJI="❌"
    fi
    curl -s -X POST "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
      -d chat_id="${{ secrets.TELEGRAM_CHAT_ID }}" \
      -d text="$EMOJI MIMIC Deploy: $STATUS"
```

Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to your GitHub secrets.

---

## ✅ Checklist

- [ ] Generated SSH key pair for deployment
- [ ] Added public key to VPS `~/.ssh/authorized_keys`
- [ ] Added `VPS_HOST` secret to GitHub
- [ ] Added `VPS_USER` secret to GitHub
- [ ] Added `VPS_SSH_KEY` secret to GitHub
- [ ] Added `VPS_PORT` secret to GitHub
- [ ] Tested manual SSH connection works
- [ ] Made a test commit to verify auto-deploy

---

**Need help?** Check the logs at `https://github.com/YOUR_USERNAME/YOUR_REPO/actions`
