#!/bin/zsh

echo "=== iOS 虛擬定位工具 安裝腳本 ==="
echo ""

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 檢查 Homebrew
if command -v brew &> /dev/null; then
    echo "✅ Homebrew 已安裝"
else
    echo "📦 安裝 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# 檢查 Python
if command -v python3 &> /dev/null; then
    echo "✅ Python 已安裝 ($(python3 --version))"
else
    echo "📦 安裝 Python..."
    brew install python
fi

# 檢查 Tkinter
if python3 -c "import tkinter" &> /dev/null; then
    echo "✅ Tkinter 已安裝"
else
    echo "📦 安裝 Tkinter..."
    brew install python-tk@3.14
fi

# 檢查 pipx
if command -v pipx &> /dev/null; then
    echo "✅ pipx 已安裝"
else
    echo "📦 安裝 pipx..."
    brew install pipx
    pipx ensurepath
    source ~/.zshrc
fi

# 檢查 pymobiledevice3
if command -v pymobiledevice3 &> /dev/null; then
    echo "✅ pymobiledevice3 已安裝"
else
    echo "📦 安裝 pymobiledevice3..."
    pipx install pymobiledevice3
fi

# 取得 Homebrew Python 路徑
PYTHON_PATH=$(brew --prefix python)/bin/python3

# 產生 .app 應用程式
APP_DIR="$SCRIPT_DIR/iOS虛擬定位.app/Contents/MacOS"
RES_DIR="$SCRIPT_DIR/iOS虛擬定位.app/Contents/Resources"
mkdir -p "$APP_DIR" "$RES_DIR"

# 複製圖示
if [ -f "$SCRIPT_DIR/AppIcon.icns" ]; then
    cp "$SCRIPT_DIR/AppIcon.icns" "$RES_DIR/AppIcon.icns"
    echo "✅ 已加入應用程式圖示"
else
    echo "⚠️ 未找到 AppIcon.icns，將使用預設圖示"
fi

cat > "$APP_DIR/iOS虛擬定位" << 'SCRIPT'
#!/bin/zsh
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$(dirname "$(dirname "$(dirname "$0")")")")" && pwd)"
PYTHON_PATH="$(brew --prefix python)/bin/python3"
cd "$SCRIPT_DIR"
"$PYTHON_PATH" app.py
SCRIPT
chmod +x "$APP_DIR/iOS虛擬定位"

cat > "$SCRIPT_DIR/iOS虛擬定位.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>iOS虛擬定位</string>
    <key>CFBundleName</key>
    <string>iOS虛擬定位</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

echo ""
echo "✅ 安裝完成！"
echo ""
echo "使用方式："
echo "1. 雙擊「iOS虛擬定位.app」開啟程式"
echo "2. iPhone 連接電腦並信任此電腦"
echo "3. iOS 17+ 需開啟：設定 > 隱私權與安全性 > 開發者模式"