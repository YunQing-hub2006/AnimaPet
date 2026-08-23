# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir 构建配置(PLAN Phase 5 第 3 项)。
#
# 使用:
#   .venv\Scripts\python -m pip install -r requirements-build.txt
#   .venv\Scripts\python tools\build_exe.py
#
# mods/ 与 data/ 是运行时数据, 由 build_exe.py 拷到 exe 旁边
# (paths.py 冻结行为: BASE_DIR = exe 所在目录)。
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("anima")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnimaPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnimaPet",
)
