#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPX_VENV="$HOME/.local/pipx/venvs/pymobiledevice3"
BREW_PYTHON="$(brew --prefix python)/bin/python3"
BUILD_VENV="$SCRIPT_DIR/.build_venv"
APP_NAME="iOS虛擬定位"

echo "=== iOS 虛擬定位 打包腳本 ==="
echo ""

# ── 1. 建立打包專用虛擬環境並安裝 PyInstaller ────────────────────
echo "▶ 建立打包虛擬環境並安裝 PyInstaller..."
"$BREW_PYTHON" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/pip" install --quiet pyinstaller

# ── 2. 打包 app.py ───────────────────────────────────────────────
echo "▶ 打包 app.py..."
cd "$SCRIPT_DIR"
"$BUILD_VENV/bin/pyinstaller" \
    --windowed \
    --name "$APP_NAME" \
    --icon AppIcon.icns \
    --noconfirm \
    --clean \
    app.py
echo "✅ app.py 打包完成"

# ── 3. 安裝 PyInstaller（pymobiledevice3 venv）──────────────────
echo ""
echo "▶ 安裝 PyInstaller（pymobiledevice3 用）..."
"$PIPX_VENV/bin/pip" install --quiet pyinstaller

# ── 4. 建立 pymobiledevice3 入口腳本 ────────────────────────────
echo "▶ 打包 pymobiledevice3..."
PMD3_ENTRY="/tmp/pmd3_entry.py"
cat > "$PMD3_ENTRY" << 'PYEOF'
import sys
from pymobiledevice3.__main__ import main
if __name__ == '__main__':
    sys.argv[0] = 'pymobiledevice3'
    sys.exit(main())
PYEOF

# ── 5. 打包 pymobiledevice3（單一執行檔）────────────────────────
"$PIPX_VENV/bin/pyinstaller" \
    --onefile \
    --name pymobiledevice3 \
    --collect-all pymobiledevice3 \
    --noconfirm \
    --clean \
    "$PMD3_ENTRY"
echo "✅ pymobiledevice3 打包完成"

# ── 6. 將凍結的 pymobiledevice3 放入 .app bundle ────────────────
echo ""
echo "▶ 組裝 .app bundle..."
TARGET_MACOS="dist/$APP_NAME.app/Contents/MacOS"
cp "dist/pymobiledevice3" "$TARGET_MACOS/pymobiledevice3"
chmod +x "$TARGET_MACOS/pymobiledevice3"
echo "✅ pymobiledevice3 已複製到 $TARGET_MACOS/"

# ── 7. 清理暫存檔與打包虛擬環境 ─────────────────────────────────
rm -f build/pymobiledevice3/pymobiledevice3.pkg \
      pymobiledevice3.spec \
      "$PMD3_ENTRY"
rm -rf "$BUILD_VENV"

echo ""
echo "======================================"
echo "✅ 打包完成！"
echo "   應用程式位於：dist/$APP_NAME.app"
echo "   直接拖到 /Applications/ 即可使用"
echo "======================================"
