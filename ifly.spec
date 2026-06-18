# -*- mode: python ; coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
from version import __version__
from PyInstaller.utils.hooks import collect_all, copy_metadata

pmd3_datas, pmd3_binaries, pmd3_hiddenimports = collect_all('pymobiledevice3')
extra_metadata = copy_metadata('pymobiledevice3')

a = Analysis(
    ['ifly.py'],
    pathex=[],
    binaries=pmd3_binaries,
    datas=pmd3_datas + extra_metadata,
    hiddenimports=pmd3_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

a_pmd3 = Analysis(
    ['tunneld_launcher.py'],
    pathex=[],
    binaries=pmd3_binaries,
    datas=pmd3_datas + extra_metadata,
    hiddenimports=pmd3_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)
pyz_pmd3 = PYZ(a_pmd3.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ifly',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_pmd3 = EXE(
    pyz_pmd3,
    a_pmd3.scripts,
    [],
    exclude_binaries=True,
    name='pymobiledevice3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    exe_pmd3,
    a.binaries,
    a_pmd3.binaries,
    a.datas,
    a_pmd3.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ifly',
)
