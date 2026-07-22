#!/usr/bin/env bash
set -e

# === konfiguracja ===
VENV_DIR=".venv"
VSCODE_DIR=".vscode"
SETTINGS_FILE="$VSCODE_DIR/settings.json"

# === sprawdź python ===
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 nie znaleziony"
  exit 1
fi

# === utwórz .venv jeśli nie istnieje ===
if [ ! -d "$VENV_DIR" ]; then
  echo "🐍 Tworzę virtualenv (.venv)"
  python3 -m venv "$VENV_DIR"
else
  echo "✅ .venv już istnieje"
fi

# === ścieżka do interpretera ===
PYTHON_PATH="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON_PATH" ]; then
  echo "❌ Nie znaleziono interpretera: $PYTHON_PATH"
  exit 1
fi

# === utwórz .vscode ===
mkdir -p "$VSCODE_DIR"

# === zapisz settings.json ===
cat > "$SETTINGS_FILE" <<EOF
{
    "python.defaultInterpreterPath": "$PYTHON_PATH"
}
EOF

echo "✅ VS Code ustawiony na interpreter: $PYTHON_PATH"
echo "🚀 Otwórz projekt poleceniem: code ."
