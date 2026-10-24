#!/usr/bin/env bash
# ==============================================================================
# info-weather uninstaller script
# Usage: uninstall.sh [--purge [--yes]]
#   --purge      also remove user data (config, cache, state, user skins)
#   --yes        skip the interactive confirmation for --purge
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PURGE=false
CONFIRM=false
for arg in "$@"; do
    case "${arg}" in
        --purge) PURGE=true ;;
        --yes) CONFIRM=true ;;
        *) echo "Unknown option: ${arg}" >&2; echo "Usage: $0 [--purge [--yes]]" >&2; exit 2 ;;
    esac
done

echo "==> Uninstalling info-weather..."

# 1. Remove binary launcher
BIN_FILE="${HOME}/.local/bin/info-weather"
if [ -L "${BIN_FILE}" ] || [ -f "${BIN_FILE}" ]; then
    rm -f "${BIN_FILE}"
    echo "  [✓] Removed ${BIN_FILE}"
fi

# 2. Remove desktop launcher (current and legacy pre-1.0 name)
DESKTOP_FILE="${HOME}/.local/share/applications/info-weather.desktop"
if [ -f "${DESKTOP_FILE}" ] || [ -L "${DESKTOP_FILE}" ]; then
    rm -f "${DESKTOP_FILE}"
    echo "  [✓] Removed ${DESKTOP_FILE}"
fi

LEGACY_DESKTOP_FILE="${HOME}/.local/share/applications/com.info.weather.desktop"
if [ -f "${LEGACY_DESKTOP_FILE}" ] || [ -L "${LEGACY_DESKTOP_FILE}" ]; then
    rm -f "${LEGACY_DESKTOP_FILE}"
    echo "  [✓] Removed legacy ${LEGACY_DESKTOP_FILE}"
fi

# 3. Remove application icon
ICON_FILE="${HOME}/.local/share/icons/hicolor/scalable/apps/info-weather.svg"
if [ -f "${ICON_FILE}" ]; then
    rm -f "${ICON_FILE}"
    echo "  [✓] Removed ${ICON_FILE}"
fi

# 4. Remove autostart entry if exists
AUTOSTART_FILE="${HOME}/.config/autostart/info-weather.desktop"
if [ -f "${AUTOSTART_FILE}" ]; then
    rm -f "${AUTOSTART_FILE}"
    echo "  [✓] Removed ${AUTOSTART_FILE}"
fi

# 5. Remove KDE Plasma KWin rules registered by install_kwinrule.sh / the app
KWINRULESRC="${HOME}/.config/kwinrulesrc"
KDE_HELPER="${SCRIPT_DIR}/../kde/install_kwinrule.sh"
if [ -f "${KWINRULESRC}" ] && [ -f "${KDE_HELPER}" ] && grep -q "info-weather" "${KWINRULESRC}" 2>/dev/null; then
    echo "  [+] Removing KDE Plasma window rules..."
    "${KDE_HELPER}" --remove || true
fi

# 6. Purge user configuration and state if requested
if [ "${PURGE}" = true ]; then
    if [ "${CONFIRM}" != true ]; then
        echo ""
        echo "  [!] Полная очистка удалит данные пользователя:"
        echo "      - ${HOME}/.config/info-weather   (конфигурация)"
        echo "      - ${HOME}/.cache/info-weather    (кэш прогнозов)"
        echo "      - ${HOME}/.local/state/info-weather (состояние)"
        echo "      - ${HOME}/.local/share/info-weather (файлы приложения и пользовательские скины)"
        echo "  Это действие необратимо."
        if [ -t 0 ]; then
            printf "  Продолжить? Введите yes: "
            read -r answer
        else
            answer=""
        fi
        if [ "${answer}" != "yes" ]; then
            echo "  [!] Полная очистка отменена."
            echo "      Для очистки без интерактивного подтверждения: $0 --purge --yes"
            exit 1
        fi
    fi
    echo "  [!] Purging user data and caches (--purge)..."
    rm -rf "${HOME}/.config/info-weather"
    rm -rf "${HOME}/.cache/info-weather"
    rm -rf "${HOME}/.local/state/info-weather"
    rm -rf "${HOME}/.local/share/info-weather"
    echo "  [✓] User configuration and cache directories removed."
else
    echo "  [*] User configuration preserved in ${HOME}/.config/info-weather (use --purge to delete)."
fi

# 7. Refresh caches
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" || true
fi

echo ""
echo "==> info-weather uninstalled successfully."
