#!/bin/bash
# ifly CLI installer — run this once after downloading the release zip
# Usage: ./install-cli.sh
set -e

IFLY_BIN="$(cd "$(dirname "$0")" && pwd)/ifly"
IFLY_LINK=/usr/local/bin/ifly
WRAPPER=/usr/local/bin/ifly-tunneld
STOP_WRAPPER=/usr/local/bin/ifly-tunneld-stop
SUDOERS_FILE=/etc/sudoers.d/ifly
USER=$(whoami)

echo "======================================="
echo " ifly CLI installer"
echo "======================================="
echo ""

# ── Step 0: verify binary ───────────────────────────────────────────────────
if [ ! -x "$IFLY_BIN" ]; then
    echo "ERROR: ifly binary not found at $IFLY_BIN"
    echo "       Make sure you run this script from the same folder as the ifly binary."
    exit 1
fi

echo "[1/5] ifly binary   : $IFLY_BIN"
echo "      Installing as : $IFLY_LINK"

# ── Step 1: install pymobiledevice3 if missing ──────────────────────────────
echo ""
echo "[2/5] Checking pymobiledevice3..."

CMD=""
for candidate in \
    "$(which pymobiledevice3 2>/dev/null)" \
    "$HOME/.local/bin/pymobiledevice3" \
    "/opt/homebrew/bin/pymobiledevice3" \
    "/usr/local/bin/pymobiledevice3"
do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        CMD="$candidate"
        break
    fi
done

if [ -z "$CMD" ]; then
    echo "      pymobiledevice3 not found — installing via pipx..."
    if ! command -v pipx &>/dev/null; then
        if command -v brew &>/dev/null; then
            echo "      Installing pipx via Homebrew..."
            brew install pipx
            pipx ensurepath
        else
            echo "ERROR: pipx is required but not installed."
            echo "       Install it first:  brew install pipx"
            exit 1
        fi
    fi
    pipx install pymobiledevice3
    # Re-check after install
    for candidate in \
        "$HOME/.local/bin/pymobiledevice3" \
        "/opt/homebrew/bin/pymobiledevice3" \
        "/usr/local/bin/pymobiledevice3"
    do
        if [ -x "$candidate" ]; then
            CMD="$candidate"
            break
        fi
    done
    if [ -z "$CMD" ]; then
        echo "ERROR: pymobiledevice3 still not found after install."
        echo "       Try opening a new terminal and running this script again."
        exit 1
    fi
    echo "      Installed: $CMD"
else
    echo "      Found: $CMD"
fi

# ── Step 2: ifly symlink ─────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing ifly to $IFLY_LINK..."
sudo ln -sf "$IFLY_BIN" "$IFLY_LINK"
echo "      Done."

# ── Step 3: tunneld wrappers ─────────────────────────────────────────────────
echo ""
echo "[4/5] Creating tunneld wrappers..."
sudo cp "$CMD" "$WRAPPER"
sudo chmod 755 "$WRAPPER"

sudo tee "$STOP_WRAPPER" > /dev/null << 'EOF'
#!/bin/sh
pkill -9 -f "pymobiledevice3 remote tunneld" 2>/dev/null || true
pkill -9 -f "ifly-tunneld remote tunneld" 2>/dev/null || true
exit 0
EOF
sudo chmod 755 "$STOP_WRAPPER"
echo "      Done."

# ── Step 4: sudoers ──────────────────────────────────────────────────────────
echo ""
echo "[5/5] Configuring passwordless sudo for tunnel..."
RULE_1="$USER ALL=(ALL) NOPASSWD: $WRAPPER"
RULE_2="$USER ALL=(ALL) NOPASSWD: $STOP_WRAPPER"

sudo tee "$SUDOERS_FILE" > /dev/null << EOF
$RULE_1
$RULE_2
EOF
sudo chmod 440 "$SUDOERS_FILE"

if ! sudo visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "ERROR: sudoers syntax check failed — removing $SUDOERS_FILE."
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi
echo "      Done."

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "======================================="
echo " Installation complete!"
echo "======================================="
echo ""
echo "Run a quick check:"
echo "  ifly doctor"
echo ""
echo "Quick start:"
echo "  ifly tunnel start"
echo "  ifly location set --lat 25.0330 --lng 121.5654"
echo ""

# Warn if pymobiledevice3 is from a non-standard path
case "$CMD" in
    *.app/*)
        echo "NOTE: pymobiledevice3 came from an app bundle ($CMD)."
        echo "      For best compatibility, install the standalone version:"
        echo "        pipx install pymobiledevice3"
        ;;
esac
