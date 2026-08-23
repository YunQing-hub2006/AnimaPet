# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本(PLAN Phase 5 第 3 项)。

生成 dist/AnimaPet/ 目录(onedir): exe + 依赖 + mods/ + data/ 目录。
"""
import argparse
import os
import shutil
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = os.path.join(_ROOT, "build.spec")
_DIST_APP = os.path.join(_ROOT, "dist", "AnimaPet")


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建 AnimaPet exe (onedir)")
    parser.add_argument("--skip-build", action="store_true",
                        help="跳过 PyInstaller, 只把 mods/data 拷进 dist")
    args = parser.parse_args(argv)

    shutil.rmtree(_DIST_APP, ignore_errors=True)
    if not args.skip_build:
        subprocess.check_call([sys.executable, "-m", "PyInstaller", _SPEC,
                               "--noconfirm", "--clean"], cwd=_ROOT)

    # 运行时数据: mods 是用户模组/内置功能模组; data 由应用运行自动创建
    shutil.copytree(os.path.join(_ROOT, "mods"),
                    os.path.join(_DIST_APP, "mods"))
    data_out = os.path.join(_DIST_APP, "data")
    os.makedirs(data_out, exist_ok=True)
    gitkeep = os.path.join(_ROOT, "data", ".gitkeep")
    if os.path.isfile(gitkeep):
        shutil.copy2(gitkeep, os.path.join(data_out, ".gitkeep"))
    print("打包完成: %s" % _DIST_APP)
    print("运行: %s" % os.path.join(_DIST_APP, "AnimaPet.exe"))
    return 0


if __name__ == "__main__":
    sys.exit(main())