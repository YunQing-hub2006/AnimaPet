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

# ---------------------------------------------------------------------------
# 瘦身: 桌宠用不到的 Qt 组件不进包
#
# opengl32sw.dll (20MB)  Mesa 软件光栅化器 —— 本应用是纯 QWidget/QPixmap,
#                        走 Qt 自带的软件后端, 从不碰 OpenGL;
# Qt6Pdf/Qt6Network(6MB) 无 PDF、无 QNetworkAccessManager(网络走 requests);
# translations (6.6MB)  96 个语言的 .qm, 界面只有简体中文, 只留 zh_CN。
#
# 合计约 32MB。注意: 只过滤 a.binaries/a.datas 里的产物, 不动 Python 层的
# import 图, 因此不会因为"少了个 dll"而 import 失败。
# ---------------------------------------------------------------------------
_JUNK_DLLS = ("opengl32sw", "Qt6Pdf", "Qt6Network")


def _drop(name):
    """返回 True = 该文件不进包。"""
    n = name.replace("\\", "/")
    for junk in _JUNK_DLLS:
        if junk in n:
            return True
    if "/translations/" in n and n.endswith(".qm"):
        return "zh_CN" not in n
    return False


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
    noarchive=False,
)
a.binaries = [b for b in a.binaries if not _drop(b[0])]
a.datas = [d for d in a.datas if not _drop(d[0])]
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
