#!/usr/bin/env bash
# ==============================================================================
# info-weather install script (user install into ~/.local, per spec)
# Usage: install.sh [--with-autostart]
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

WITH_AUTOSTART=false
if [ "${1:-}" = "--with-autostart" ]; then
    WITH_AUTOSTART=true
elif [ -n "${1:-}" ]; then
    echo "Usage: $0 [--with-autostart]" >&2
    exit 2
fi

echo "==> Installing info-weather..."

# 1. Install application files into ~/.local/share/info-weather.
# Only app-owned directories are replaced; user data (e.g. skins/) is preserved.
APP_DIR="${HOME}/.local/share/info-weather"
mkdir -p "${APP_DIR}"
for dir in core models providers data ui assets; do
    rm -rf "${APP_DIR}/${dir}"
    cp -r "${PROJECT_ROOT}/${dir}" "${APP_DIR}/${dir}"
done
for f in main.py NOTICE README.md LICENSE; do
    cp -f "${PROJECT_ROOT}/${f}" "${APP_DIR}/${f}"
done
find "${APP_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "${APP_DIR}/main.py"
echo "  [✓] Application installed to ${APP_DIR}"

# 2. Install CLI launcher
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"
cat > "${BIN_DIR}/info-weather" << 'EOF'
#!/bin/sh
exec python3 "${HOME}/.local/share/info-weather/main.py" "$@"
EOF
chmod +x "${BIN_DIR}/info-weather"
echo "  [✓] Launcher installed to ${BIN_DIR}/info-weather"

# 3. Install Desktop Launcher
APPS_DIR="${HOME}/.local/share/applications"
mkdir -p "${APPS_DIR}"
sed -e "s|^Exec=info-weather|Exec=${BIN_DIR}/info-weather|" \
    -e "s|^TryExec=info-weather|TryExec=${BIN_DIR}/info-weather|" \
    "${PROJECT_ROOT}/packaging/info-weather.desktop" > "${APPS_DIR}/info-weather.desktop"
chmod +x "${APPS_DIR}/info-weather.desktop"
echo "  [✓] Installed desktop launcher to ${APPS_DIR}/info-weather.desktop"

# 4. Install Application Icon
ICONS_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
mkdir -p "${ICONS_DIR}"
cp "${PROJECT_ROOT}/assets/icons/info-weather.svg" "${ICONS_DIR}/info-weather.svg"
echo "  [✓] Installed application icon to ${ICONS_DIR}/info-weather.svg"

# 5. Install KDE Plasma KWin Rule (keep widget visible on Meta+D)
if command -v qdbus >/dev/null 2>&1 || command -v qdbus6 >/dev/null 2>&1 || [ -f "${HOME}/.config/kwinrulesrc" ]; then
    echo "  [+] Configuring KDE Plasma window rules..."
    "${PROJECT_ROOT}/packaging/kde/install_kwinrule.sh" || true
fi

# 6. Optional autostart entry
if [ "${WITH_AUTOSTART}" = true ]; then
    AUTOSTART_DIR="${HOME}/.config/autostart"
    mkdir -p "${AUTOSTART_DIR}"
    cat > "${AUTOSTART_DIR}/info-weather.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Info Weather
Exec=${BIN_DIR}/info-weather --autostart --delay 3
X-GNOME-Autostart-enabled=true
EOF
    echo "  [✓] Autostart entry installed to ${AUTOSTART_DIR}/info-weather.desktop"
fi

# 7. Update Desktop Database & Icon Cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo ""
echo "==> Installation complete!"
echo "You can now run 'info-weather' from terminal or launch it from application menu."
if [ "${WITH_AUTOSTART}" != true ]; then
    echo "Tip: re-run with --with-autostart to launch the widget on login."
fi
