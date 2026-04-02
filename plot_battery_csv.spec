# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for plot_battery_csv
Works on both macOS and Windows — build on each target OS.

Usage:
    pyinstaller plot_battery_csv.spec

Output:
    dist/BatteryPlotter/          (folder bundle)
        BatteryPlotter(.exe)      (main executable)
        + supporting libs
"""

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Matplotlib ships backends and data (fonts, stylesheets) that must be bundled
matplotlib_hiddenimports = collect_submodules('matplotlib')
matplotlib_datas = collect_data_files('matplotlib')

# Pandas uses some optional C-extension backends
pandas_hiddenimports = collect_submodules('pandas')

block_cipher = None

a = Analysis(
    ['plot_battery_csv.py'],
    pathex=[],
    binaries=[],
    datas=matplotlib_datas,
    hiddenimports=matplotlib_hiddenimports + pandas_hiddenimports + [
        'tkinter',
        'tkinter.filedialog',
        '_tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim things we don't need to keep the bundle smaller
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'IPython', 'notebook', 'sphinx',
        'pytest', 'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                   # NOT onefile — collect into folder
    exclude_binaries=True,
    name='BatteryPlotter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,         # Keep console for the interactive menu
    disable_windowed_traceback=False,
    argv_emulation=True if sys.platform == 'darwin' else False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BatteryPlotter',
)

# macOS .app bundle (ignored on Windows)
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='BatteryPlotter.app',
        icon=None,
        bundle_identifier='com.batteryplotter.app',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
        },
    )
