# Git Clone Command

## Clone MIMIC Repository from GitHub

```bash
git clone https://github.com/mimiccash-ops/MIMIC.git
```

### Clone to Specific Directory

```bash
git clone https://github.com/mimiccash-ops/MIMIC.git /var/www/mimic
```

### Clone Specific Branch

```bash
git clone -b main https://github.com/mimiccash-ops/MIMIC.git
```

### Clone with SSH (if you have SSH keys configured)

```bash
git clone git@github.com:mimiccash-ops/MIMIC.git
```

---

## Quick Setup After Cloning

After cloning, navigate to the directory and run the automated installation script:

```bash
cd MIMIC
chmod +x install_vps.sh
sudo ./install_vps.sh
```

Or use the existing deployment guide:

```bash
cd MIMIC
# Follow instructions in LINUX_DEPLOYMENT.md
```
