#!/bin/bash
# =============================================================================
# Brain Capital - Configuration Helper
# =============================================================================
# This script validates your settings and generates config files
# =============================================================================

echo ""
echo " ============================================"
echo "  Brain Capital - Configuration Helper"
echo " ============================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3.8+ with: apt install python3"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if admin_settings.ini exists
if [ ! -f "admin_settings.ini" ]; then
    echo "[INFO] admin_settings.ini not found"
    echo "[INFO] Please create and fill in admin_settings.ini"
    exit 1
fi

echo "[INFO] Validating settings..."
echo ""

python3 validate_settings.py --generate

echo ""

