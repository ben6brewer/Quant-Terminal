#!/bin/bash
set -euo pipefail

# -------------------------------------------------------------------
# Quant Terminal - macOS Build Script
#
# Produces:
#   dist/Quant Terminal.app   (standalone application bundle)
#   dist/QuantTerminal.dmg    (optional disk image for distribution)
#
# Usage:
#   bash build_macos.sh          # build only
#   bash build_macos.sh --dmg    # build + create DMG
# -------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_DMG=false
if [[ "${1:-}" == "--dmg" ]]; then
    BUILD_DMG=true
fi

echo "==> Creating build virtual environment..."
python3 -m venv build_venv
source build_venv/bin/activate

echo "==> Installing dependencies..."
pip install --upgrade pip
pip install -e .
pip install "pyinstaller>=6.0"

echo "==> Running PyInstaller..."
pyinstaller quant_terminal.spec --noconfirm

echo "==> Build complete: dist/Quant Terminal.app"

if $BUILD_DMG; then
    echo "==> Creating DMG..."
    DMG_NAME="QuantTerminal_macOS_$(uname -m).dmg"
    hdiutil create -volname "Quant Terminal" \
        -srcfolder "dist/Quant Terminal.app" \
        -ov -format UDZO \
        "dist/$DMG_NAME"
    echo "==> DMG created: dist/$DMG_NAME"
fi

deactivate
echo "==> Done."
