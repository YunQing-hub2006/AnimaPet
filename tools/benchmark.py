# -*- coding: utf-8 -*-
"""AnimaPet 全栈性能基准(PLAN Phase 5 第 4 项)。

测量: 完整官方插件栈 + 真实 mods 的启动耗时与 Python 峰值内存(offscreen)。
用法: .venv\\Scripts\\python tools\\benchmark.py
"""
import asyncio
import os
import sys
import time
import tracemalloc

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as app_main  # noqa: E402


def run() -> int:
    from PyQt6.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication([])
    app_main._configure_qt(qapp)

    core, plugins, pet, _bridge = app_main._build_stack()
    tracemalloc.start()
    t0 = time.perf_counter()
    asyncio.run(core.start(plugins))
    startup_s = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_mods = len(core.registry.use("mods").all_mods)
    print("startup  : %.3f s (目标 < 3s)" % startup_s)
    print("pythonmem: current %.1f MiB / peak %.1f MiB" % (current / 1024 / 1024, peak / 1024 / 1024))
    print("mods     : %d 个模组对象" % total_mods)
    asyncio.run(core.stop())
    print("目标     : 启动 < 3s; 内存与 YingPet 持平(待真机对比)")
    return 0 if startup_s < 3.0 else 1


if __name__ == "__main__":
    sys.exit(run())