# Push Local Code to GitHub

The GitHub repository appears to be empty. You need to push your local code first.

## Option 1: Push to GitHub (Recommended)

### On Windows (PowerShell):

```powershell
# Make script executable (if using Git Bash or WSL)
bash push_to_github.sh

# Or manually:
git init
git remote add origin https://github.com/mimiccash-ops/MIMIC.git
git add .
git commit -m "Initial commit: MIMIC v4.0"
git branch -M main
git push -u origin main
```

### On Linux/Mac:

```bash
chmod +x push_to_github.sh
./push_to_github.sh
```

**Note:** You may need to authenticate with GitHub:
- Use a Personal Access Token (Settings → Developer settings → Personal access tokens)
- Or use SSH: `git remote set-url origin git@github.com:mimiccash-ops/MIMIC.git`

---

## Option 2: Deploy Directly to VPS (No GitHub Needed)

If you don't want to use GitHub, you can copy files directly to your VPS:

### On Windows (using WSL or Git Bash):

```bash
chmod +x deploy_direct_to_vps.sh
./deploy_direct_to_vps.sh root@YOUR_VPS_IP
```

### On Linux/Mac:

```bash
chmod +x deploy_direct_to_vps.sh
./deploy_direct_to_vps.sh root@YOUR_VPS_IP
```

This will:
1. Copy all files to your VPS using rsync
2. Run the installation script automatically

---

## Option 3: Manual Copy (Simple)

### Using SCP (from your local machine):

```bash
# Copy entire directory
scp -r * root@YOUR_VPS_IP:/var/www/mimic/

# Then on VPS:
ssh root@YOUR_VPS_IP
cd /var/www/mimic
chmod +x install_vps.sh
sudo ./install_vps.sh
```

### Using rsync (more efficient):

```bash
rsync -avz --exclude='venv' --exclude='.git' --exclude='*.db' \
  ./ root@YOUR_VPS_IP:/var/www/mimic/
```

---

## After Pushing to GitHub

Once your code is on GitHub, you can clone on your VPS:

```bash
git clone https://github.com/mimiccash-ops/MIMIC.git /var/www/mimic
cd /var/www/mimic
sudo chmod +x install_vps.sh
sudo ./install_vps.sh
```

---

## GitHub Authentication

If you get authentication errors:

1. **Use Personal Access Token:**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `repo` scope
   - Use token as password when pushing

2. **Use SSH:**
   ```bash
   git remote set-url origin git@github.com:mimiccash-ops/MIMIC.git
   ```

3. **Use GitHub CLI:**
   ```bash
   gh auth login
   ```
