#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYINSTALLER="$HOME/.local/pipx/venvs/pymobiledevice3/bin/pyinstaller"

echo "=== iOS 虛擬定位 打包腳本 ==="
echo ""

cd "$SCRIPT_DIR"
"$PYINSTALLER" iOS虛擬定位.spec

echo ""
echo "======================================"
echo "✅ 打包完成！"
echo "   應用程式位於：dist/iOS虛擬定位.app"
echo "   直接拖到 /Applications/ 即可使用"
echo "======================================"
