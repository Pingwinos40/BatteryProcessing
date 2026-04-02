#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# build.sh — Build BatteryPlotter standalone executable
# Works on macOS and Linux.  For Windows, use build.bat.
# ──────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== BatteryPlotter Build ==="
echo "Platform: $(uname -s) $(uname -m)"
echo ""

# ── 1. Create/activate a venv so we don't pollute the system Python ──
VENV_DIR="$SCRIPT_DIR/.venv_build"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating build virtualenv..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# ── 2. Install dependencies ─────────────────────────────────────────
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 3. Run PyInstaller ──────────────────────────────────────────────
echo ""
echo "Running PyInstaller..."
pyinstaller --clean --noconfirm plot_battery_csv.spec

# ── 4. Report ────────────────────────────────────────────────────────
echo ""
echo "=== Build complete ==="
if [ -d "dist/BatteryPlotter" ]; then
    SIZE=$(du -sh dist/BatteryPlotter | cut -f1)
    echo "Output:  dist/BatteryPlotter/  ($SIZE)"
    echo ""
    echo "Usage:"
    echo "  ./dist/BatteryPlotter/BatteryPlotter <your_data.csv>"
    echo ""
    echo "To distribute: zip or tar the dist/BatteryPlotter/ folder."
fi

if [ -d "dist/BatteryPlotter.app" ]; then
    echo ""
    echo "macOS app bundle:  dist/BatteryPlotter.app"
    echo "  (Note: this is a CLI tool — run from Terminal, not Finder)"
fi

deactivate
