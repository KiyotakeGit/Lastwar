# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Last War Automation
# Build command: pyinstaller lastwar.spec
# Output: dist/LastWarAutomation.exe (single file)

block_cipher = None

a = Analysis(
    ['lastwar.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'src.device.pc',
        'src.device.android',
        'src.gui.app',
        'src.gui.canvas_panel',
        'src.gui.match_panel',
        'src.gui.region_panel',
        'src.gui.state_panel',
        'src.gui.task_panel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LastWarAutomation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # No console window, GUI only
    icon=None,           # Set to 'icon.ico' if you have one
)
