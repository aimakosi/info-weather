#!/usr/bin/env bash
# Script to install/remove the KDE KWin rule for info-weather.
# The canonical rule content lives in info-weather.kwinrule next to this script;
# this script merges it into ~/.config/kwinrulesrc (allocating a free numeric ID).
# Usage: install_kwinrule.sh [--remove]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULE_TEMPLATE="${SCRIPT_DIR}/info-weather.kwinrule"

MODE="install"
if [ "${1:-}" = "--remove" ]; then
    MODE="remove"
elif [ -n "${1:-}" ]; then
    echo "Usage: $0 [--remove]" >&2
    exit 2
fi

if [ ! -f "${RULE_TEMPLATE}" ]; then
    echo "Ошибка: файл шаблона правила ${RULE_TEMPLATE} не найден!" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Ошибка: для управления правилами KWin требуется python3" >&2
    exit 1
fi

if [ "${MODE}" = "install" ]; then
    echo "==> Установка и регистрация правила KWin для info-weather..."
else
    echo "==> Удаление правила KWin для info-weather..."
fi

MODE="${MODE}" KWINRULE_TEMPLATE="${RULE_TEMPLATE}" python3 - << 'EOF'
import configparser
import os
import sys

mode = os.environ.get("MODE", "install")
template_path = os.environ.get("KWINRULE_TEMPLATE", "")
kwinrc = os.path.expanduser("~/.config/kwinrulesrc")

# Load the canonical rule section from the template file.
tpl = configparser.ConfigParser(interpolation=None)
tpl.optionxform = str
try:
    with open(template_path, "r", encoding="utf-8") as f:
        tpl.read_file(f)
except OSError as e:
    print(f"Ошибка: не удалось прочитать шаблон правила {template_path}: {e}", file=sys.stderr)
    sys.exit(1)

rule_section_name = next((s for s in tpl.sections() if s != "General"), None)
if rule_section_name is None:
    print("Ошибка: в шаблоне правила нет секций с содержимым", file=sys.stderr)
    sys.exit(1)
rule_props = {k: v for k, v in tpl.items(rule_section_name)}

parser = configparser.ConfigParser(interpolation=None)
parser.optionxform = str
if os.path.isfile(kwinrc):
    try:
        with open(kwinrc, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if content.strip():
            parser.read_string(content)
    except Exception as e:
        print(f"Предупреждение: ошибка чтения {kwinrc}: {e}")


def is_weather_section(parser: configparser.ConfigParser, sec: str) -> bool:
    """Detect rule sections that belong to info-weather (same criteria on install and remove)."""
    if sec == "General":
        return False
    if "info-weather" in sec:
        return True
    for key in ("wmclass", "Description", "title"):
        if parser.has_option(sec, key) and "info-weather" in parser.get(sec, key):
            return True
    return False


def rebuild_rules_list(parser: configparser.ConfigParser) -> list[str]:
    """Rebuild [General].rules keeping every non-General section that exists,
    preserving the original order and appending any sections that were not listed."""
    rules_str = parser.get("General", "rules", fallback="").strip()
    result = [r.strip() for r in rules_str.split(",") if r.strip() and parser.has_section(r)]
    listed = set(result)
    for sec in parser.sections():
        if sec != "General" and sec not in listed:
            result.append(sec)
    return result


weather_sections = [s for s in list(parser.sections()) if is_weather_section(parser, s)]

if mode == "remove":
    if not weather_sections:
        print("Правила info-weather не найдены — удалять нечего.")
        sys.exit(0)
    for sec in weather_sections:
        parser.remove_section(sec)
    if parser.has_section("General"):
        remaining = rebuild_rules_list(parser)
        parser.set("General", "rules", ",".join(remaining))
        int_ids = [int(s) for s in parser.sections() if s.isdigit()]
        parser.set("General", "count", str(max(int_ids, default=0)))
    with open(kwinrc, "w", encoding="utf-8") as f:
        parser.write(f)
    print(f"Удалены правила: {', '.join(weather_sections)}. Файл обновлён: {kwinrc}")
    sys.exit(0)

# --- install mode: replace all existing info-weather sections with the template one ---
os.makedirs(os.path.dirname(kwinrc), exist_ok=True)
if not parser.has_section("General"):
    parser.add_section("General")

for sec in weather_sections:
    parser.remove_section(sec)

rules_list = rebuild_rules_list(parser)

int_ids = [int(s) for s in parser.sections() if s.isdigit()]
next_id = max(int_ids, default=0) + 1
parser.add_section(str(next_id))
for k, v in rule_props.items():
    parser.set(str(next_id), k, v)
rules_list.append(str(next_id))

parser.set("General", "rules", ",".join(rules_list))
parser.set("General", "count", str(max(max(int_ids, default=0), next_id)))

with open(kwinrc, "w", encoding="utf-8") as f:
    parser.write(f)

print(f"Правило info-weather зарегистрировано в {kwinrc} (секция [{next_id}]).")
EOF

# Перезагрузка правил KWin без перезапуска сессии
if command -v qdbus6 >/dev/null 2>&1; then
    qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null || true
fi
if command -v qdbus >/dev/null 2>&1; then
    qdbus org.kde.KWin /KWin reconfigure 2>/dev/null || qdbus org.kde.KWin /KWin org.kde.KWin.reconfigure 2>/dev/null || true
fi

if [ "${MODE}" = "install" ]; then
    echo "==> Готово. Правило KWin для info-weather зарегистрировано."
else
    echo "==> Готово. Правила KWin для info-weather удалены."
fi
