#!/usr/bin/env bash
set -euo pipefail

APP_NAME="LowCore Client"
INSTALL_DIR="$HOME/.local/share/lowcoreclient"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  LowCore Client — Linux Installer"
echo "=========================================="

# Locate the compiled executable inside the extracted folder
SRC_BIN=""
for candidate in "LowCoreClient" "LowCoreClient.bin" "main.bin" "main"; do
  if [ -f "$SCRIPT_DIR/$candidate" ]; then
    SRC_BIN="$candidate"
    break
  fi
done

if [ -z "$SRC_BIN" ]; then
  echo "Error: Could not find LowCoreClient executable in $SCRIPT_DIR."
  echo "Make sure you extracted the entire LowCoreClient-Linux.zip before running install.sh."
  exit 1
fi

# Install required Qt6 XCB cursor runtime library on Debian/Ubuntu if missing
if command -v apt-get >/dev/null 2>&1; then
  if ! dpkg -s libxcb-cursor0 >/dev/null 2>&1; then
    echo "Installing required Qt6 library (libxcb-cursor0)..."
    sudo apt-get update && sudo apt-get install -y libxcb-cursor0
  fi
elif command -v dnf >/dev/null 2>&1; then
  if ! rpm -q xcb-util-cursor >/dev/null 2>&1; then
    echo "Installing required Qt6 library (xcb-util-cursor)..."
    sudo dnf install -y xcb-util-cursor
  fi
elif command -v pacman >/dev/null 2>&1; then
  if ! pacman -Qi xcb-util-cursor >/dev/null 2>&1; then
    echo "Installing required Qt6 library (xcb-util-cursor)..."
    sudo pacman -S --noconfirm xcb-util-cursor
  fi
fi

echo "Installing files to $INSTALL_DIR ..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR"
cp -a "$SCRIPT_DIR/." "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/$SRC_BIN"
if [ -f "$INSTALL_DIR/install.sh" ]; then
  chmod +x "$INSTALL_DIR/install.sh"
fi

# Create wrapper command in ~/.local/bin/lowcoreclient
cat > "$BIN_DIR/lowcoreclient" <<EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/$SRC_BIN" "\$@"
EOF
chmod +x "$BIN_DIR/lowcoreclient"

# Pick icon if present
ICON_PATH=""
for icon in "$INSTALL_DIR/assets/logo.png" "$INSTALL_DIR/assets/logo.ico"; do
  if [ -f "$icon" ]; then
    ICON_PATH="$icon"
    break
  fi
done

# Create desktop shortcut for application menus
cat > "$DESKTOP_DIR/lowcoreclient.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Minimalist High-FPS Minecraft Client
Exec=$BIN_DIR/lowcoreclient
Path=$INSTALL_DIR
Terminal=false
Categories=Game;
EOF

if [ -n "$ICON_PATH" ]; then
  echo "Icon=$ICON_PATH" >> "$DESKTOP_DIR/lowcoreclient.desktop"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo ""
echo "Installed successfully!"
echo "  Run from menu:   LowCore Client"
echo "  Run in terminal: $BIN_DIR/lowcoreclient"
echo ""
echo "Troubleshooting: If Qt says 'xcb' failed to load, run:"
echo "  sudo apt update && sudo apt install -y libxcb-cursor0"
