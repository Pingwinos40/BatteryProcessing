# Building BatteryPlotter as a Standalone Executable

PyInstaller **cannot cross-compile** — you must build on the target OS.

## Prerequisites

- Python 3.10+ installed and on PATH
- `tkinter` available (comes with standard Python on macOS/Windows;
  on Linux you may need `sudo apt install python3-tk`)

## Quick Start

### macOS / Linux

```bash
chmod +x build.sh
./build.sh
```

### Windows

```cmd
build.bat
```

That's it. The build script creates a virtualenv, installs everything, and
runs PyInstaller automatically.

## Output

```
dist/
  BatteryPlotter/          ← folder bundle (distribute this whole folder)
    BatteryPlotter(.exe)   ← main executable
    ...                    ← supporting libraries
  BatteryPlotter.app/      ← macOS only: .app bundle (same thing, wrapped)
```

## Usage (for end users)

The end user does NOT need Python installed. They just run:

```bash
# macOS / Linux
./BatteryPlotter path/to/data.csv

# Windows
BatteryPlotter.exe path\to\data.csv
```

The interactive menu will appear in the terminal. All CLI flags
(`--preset`, `--per-cycle`, etc.) work exactly as before.

## Distribution

Zip or tar the entire `dist/BatteryPlotter/` folder and send it to
your users. On macOS you can alternatively distribute
`dist/BatteryPlotter.app`.

**Note:** The macOS `.app` bundle is still a terminal application — it
should be launched from Terminal, not double-clicked in Finder (Finder
would open it but you wouldn't see the interactive menu).

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` at runtime | Add the missing module to `hiddenimports` in `plot_battery_csv.spec` |
| Tkinter not found during build | Install `python3-tk` (Linux) or reinstall Python with Tcl/Tk (macOS via python.org) |
| Build fails on Apple Silicon | Use `python3` from python.org (universal2) or Homebrew; Conda sometimes has issues |
| Bundle is very large (>500 MB) | Add unused packages to `excludes` list in the .spec file |
| Windows Defender flags the .exe | This is a common false positive with PyInstaller; you can sign the binary or add an exception |
