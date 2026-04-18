#!/bin/bash
set -e

WRAPPER=/usr/local/bin/ifly-tunneld
STOP_WRAPPER=/usr/local/bin/ifly-tunneld-stop
SUDOERS_FILE=/etc/sudoers.d/ifly
USER=$(whoami)

# Find pymobiledevice3 — check system PATH first, then common locations, then app bundle
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

# 1. Start wrapper
echo "[1/3] Creating start wrapper at $WRAPPER..."
sudo cp "$CMD" "$WRAPPER"
sudo chmod 755 "$WRAPPER"
echo "     Done."

# 2. Stop wrapper
echo "[2/3] Creating stop wrapper at $STOP_WRAPPER..."
sudo tee "$STOP_WRAPPER" > /dev/null << 'EOF'
#!/bin/sh
pkill -9 -f "pymobiledevice3 remote tunneld" 2>/dev/null || true
pkill -9 -f "ifly-tunneld remote tunneld" 2>/dev/null || true
exit 0
EOF
sudo chmod 755 "$STOP_WRAPPER"
echo "     Done."

# 3. sudoers
echo "[3/3] Writing sudoers rule to $SUDOERS_FILE..."
RULE_1="$USER ALL=(ALL) NOPASSWD: $WRAPPER"
RULE_2="$USER ALL=(ALL) NOPASSWD: $STOP_WRAPPER"

sudo tee "$SUDOERS_FILE" > /dev/null << EOF
$RULE_1
$RULE_2
EOF
sudo chmod 440 "$SUDOERS_FILE"

# Validate with visudo
if ! sudo visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "ERROR: sudoers syntax check failed. Removing $SUDOERS_FILE."
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi
echo "     Done."

echo ""
echo "Setup complete. Run the following to verify:"
echo "  python3 ifly.py doctor"
echo ""

# Warn if using bundled binary
case "$CMD" in
    *.app/*)
        echo "WARNING: Using pymobiledevice3 from app bundle ($CMD)."
        echo "         For best results, install the system version:"
        echo "           pipx install pymobiledevice3"
        ;;
esac
