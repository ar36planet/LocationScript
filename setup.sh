#!/bin/bash
# Developer setup — links source ifly.py into PATH and configures sudoers.
# For packaged-binary installs, use install-cli.sh instead.
set -e

WRAPPER=/usr/local/bin/ifly-tunneld
STOP_WRAPPER=/usr/local/bin/ifly-tunneld-stop
SUDOERS_FILE=/etc/sudoers.d/ifly
USER=$(whoami)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IFLY_BIN="$SCRIPT_DIR/dist/ifly/ifly"
IFLY_PY="$SCRIPT_DIR/ifly.py"
IFLY_LINK=/usr/local/bin/ifly

# Find pymobiledevice3
CMD=$(which pymobiledevice3 2>/dev/null || true)
if [ -z "$CMD" ]; then
    for candidate in \
        "$HOME/.local/bin/pymobiledevice3" \
        "/opt/homebrew/bin/pymobiledevice3" \
        "/usr/local/bin/pymobiledevice3" \
        "/Applications/iOS虛擬定位.app/Contents/MacOS/pymobiledevice3"
    do
        if [ -x "$candidate" ]; then
            CMD="$candidate"
            break
        fi
    done
fi

if [ -z "$CMD" ]; then
    echo "ERROR: pymobiledevice3 not found. Install it first:"
    echo "  pipx install pymobiledevice3"
    exit 1
fi

echo "==> Using pymobiledevice3 at: $CMD"
echo "==> Setting up for user: $USER"
echo ""

# 1. ifly symlink
echo "[1/4] Creating ifly symlink at $IFLY_LINK..."
if [ -x "$IFLY_BIN" ]; then
    IFLY_SRC="$IFLY_BIN"
    echo "     Using packaged binary: $IFLY_SRC"
else
    IFLY_SRC="$IFLY_PY"
    chmod +x "$IFLY_SRC"
    echo "     Using source script: $IFLY_SRC"
fi
sudo ln -sf "$IFLY_SRC" "$IFLY_LINK"
echo "     Done."

echo "[2/4] Creating start wrapper at $WRAPPER..."
sudo cp "$CMD" "$WRAPPER"
sudo chmod 755 "$WRAPPER"
echo "     Done."

echo "[3/4] Creating stop wrapper at $STOP_WRAPPER..."
sudo tee "$STOP_WRAPPER" > /dev/null << 'EOF'
#!/bin/sh
pkill -9 -f "pymobiledevice3 remote tunneld" 2>/dev/null || true
pkill -9 -f "ifly-tunneld remote tunneld" 2>/dev/null || true
exit 0
EOF
sudo chmod 755 "$STOP_WRAPPER"
echo "     Done."

echo "[4/4] Writing sudoers rule to $SUDOERS_FILE..."
RULE_1="$USER ALL=(ALL) NOPASSWD: $WRAPPER"
RULE_2="$USER ALL=(ALL) NOPASSWD: $STOP_WRAPPER"

sudo tee "$SUDOERS_FILE" > /dev/null << EOF
$RULE_1
$RULE_2
EOF
sudo chmod 440 "$SUDOERS_FILE"

if ! sudo visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "ERROR: sudoers syntax check failed. Removing $SUDOERS_FILE."
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi
echo "     Done."

echo ""
echo "Setup complete. Run the following to verify:"
echo "  ifly doctor"
echo ""

case "$CMD" in
    *.app/*)
        echo "WARNING: Using pymobiledevice3 from app bundle ($CMD)."
        echo "         For best results, install the system version:"
        echo "           pipx install pymobiledevice3"
        ;;
esac
