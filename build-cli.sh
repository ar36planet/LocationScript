#!/bin/bash
# Builds the ifly standalone binary (onefile) and packages it for distribution.
# Output: dist/ifly-<version>-macos.zip
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(python3 -c "from version import __version__; print(__version__)")
RELEASE_DIR="$SCRIPT_DIR/dist/release"
ZIP_NAME="ifly-${VERSION}-macos.zip"

echo "=== Building ifly CLI v${VERSION} ==="
echo ""

# 1. Run PyInstaller
echo "[1/3] Running PyInstaller..."
PYINSTALLER=$(find "$HOME/.local/pipx/venvs" -name pyinstaller -type f 2>/dev/null | head -1)
if [ -z "$PYINSTALLER" ]; then
    PYINSTALLER=$(which pyinstaller 2>/dev/null || true)
fi
if [ -z "$PYINSTALLER" ]; then
    echo "ERROR: pyinstaller not found."
    echo "  pipx inject pymobiledevice3 pyinstaller"
    exit 1
fi
"$PYINSTALLER" ifly.spec --noconfirm
echo ""

# 2. Assemble release folder
echo "[2/3] Assembling release package..."
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
cp "$SCRIPT_DIR/dist/ifly" "$RELEASE_DIR/ifly"
chmod +x "$RELEASE_DIR/ifly"
echo "    Ad-hoc signing..."
codesign --force --deep --sign - "$RELEASE_DIR/ifly"

# 3. Zip
echo "[3/3] Creating $ZIP_NAME..."
cd "$SCRIPT_DIR/dist"
zip "$ZIP_NAME" release/ifly
echo ""
echo "======================================="
echo " Done!  dist/$ZIP_NAME"
echo "======================================="
echo ""
echo "Distribute this zip. Users install with:"
echo "  unzip $ZIP_NAME"
echo "  ./release/ifly install"
