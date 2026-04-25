# -*- mode: python ; coding: utf-8 -*-
import shutil
import sys
sys.path.insert(0, '.')
from version import __version__

# Bundle the system pymobiledevice3 binary inside ifly
_pmd3 = shutil.which('pymobiledevice3')
_extra_binaries = [(_pmd3, '.')] if _pmd3 else []

a = Analysis(
    ['ifly.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
