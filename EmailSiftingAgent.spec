# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files


ttkbootstrap_data = collect_data_files("ttkbootstrap")

analysis = Analysis(
    ["appROOT.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("resources", "resources"),
        ("app/user/useroptions.json", "app/user"),
        *ttkbootstrap_data,
    ],
    hiddenimports=[
        "app",
        "app.microsoftGraph",
        "app.microsoftGraph.email",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="EmailSiftingAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
