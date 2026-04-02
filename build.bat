@echo off
REM ──────────────────────────────────────────────────────────
REM build.bat — Build BatteryPlotter standalone executable
REM For Windows.  Run from Command Prompt or PowerShell.
REM ──────────────────────────────────────────────────────────

echo === BatteryPlotter Build (Windows) ===
echo.

REM ── 1. Create/activate venv ────────────────────────────────
if not exist ".venv_build" (
    echo Creating build virtualenv...
    python -m venv .venv_build
)
call .venv_build\Scripts\activate.bat

REM ── 2. Install dependencies ────────────────────────────────
echo Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q

REM ── 3. Run PyInstaller ─────────────────────────────────────
echo.
echo Running PyInstaller...
pyinstaller --clean --noconfirm plot_battery_csv.spec

REM ── 4. Report ──────────────────────────────────────────────
echo.
echo === Build complete ===
if exist "dist\BatteryPlotter" (
    echo Output:  dist\BatteryPlotter\
    echo.
    echo Usage:
    echo   dist\BatteryPlotter\BatteryPlotter.exe your_data.csv
    echo.
    echo To distribute: zip the dist\BatteryPlotter\ folder.
)

call deactivate
