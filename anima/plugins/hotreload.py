# -*- coding: utf-8 -*-
"""hotreload 插件: mods/ 目录热加载(拖入/删除模组文件夹 → 自动重扫)。

设计(TD1 约束):
- ``ModsWatcher`` 是 QObject, **必须在 Qt 主线程创建**(enable 阶段经
  bridge.run_on_ui 保证), 否则 directoryChanged 信号会投递到内核线程的
  事件循环(那里没有 Qt 循环, 信号永远不送达);
- 文件系统事件连发 → 800ms 防抖 → 回调 ``module_manager.rescan()``
  (线程感知: Qt 线程调用会被调度到内核循环执行, 注册表重建不竞态);
- 窗口刷新/规则重订阅/feature 对账由 mods.reloaded 事件的既有订阅者完成
  (bridge/rule_engine/module_manager), 本插件只负责"何时触发重扫"。

搬自 YingPet-v4 harness 的 watcher 编排(_refresh_watch_paths/_on_fs_changed/
_do_debounced_reload), 差异: reload 动作改为经 module_manager 服务调度。
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer

from anima.core import Context, Plugin
from anima.utils import log, paths

_log = log.get("hotreload")


class ModsWatcher(QObject):
    """mods/ 目录树监听 + 防抖重扫(仅 Qt 主线程使用)。"""

    def __init__(self, mods_dir: str, debounce_ms: int = 800, rescan=None) -> None:
        super().__init__()
        self._mods_dir = str(mods_dir)
        self._rescan = rescan
        self._pending = False
        self._fs = QFileSystemWatcher(self)
        self._fs.directoryChanged.connect(self._on_dir_changed)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(50, int(debounce_ms)))
        self._timer.timeout.connect(self._do_reload)

    def set_rescan(self, fn) -> None:
        self._rescan = fn

    # -- 启停 -------------------------------------------------------------

    def start(self) -> None:
        self._refresh_paths()
        _log.info("mods watcher started: %s", self._mods_dir)

    def stop(self) -> None:
        self._timer.stop()
        self._pending = False
        for p in list(self._fs.directories()):
            self._fs.removePath(p)
        _log.info("mods watcher stopped")

    def _refresh_paths(self) -> None:
        for p in list(self._fs.directories()):
            self._fs.removePath(p)
        if os.path.isdir(self._mods_dir):
            self._fs.addPath(self._mods_dir)
            for name in sorted(os.listdir(self._mods_dir)):
                d = os.path.join(self._mods_dir, name)
                if os.path.isdir(d):
                    self._fs.addPath(d)

    # -- 防抖 -------------------------------------------------------------

    def _on_dir_changed(self, _path) -> None:
        if self._pending:
            return
        self._pending = True
        self._timer.start()

    def _do_reload(self) -> None:
        self._pending = False
        try:
            self._refresh_paths()
        except Exception as e:
            _log.warning("watch paths refresh: %s", e)
        if self._rescan is None:
            return
        try:
            self._rescan()
        except Exception as e:
            _log.warning("hot reload failed: %s", e)


class HotreloadPlugin(Plugin):
    """热加载插件: enable 时在 Qt 线程起 watcher, 改动即重扫。"""

    name = "hotreload"
    version = "1.0.0"
    dependencies = ["module_manager"]

    def __init__(self, watcher: ModsWatcher | None = None, debounce_ms: int = 800) -> None:
        self._watcher = watcher
        self._debounce_ms = debounce_ms
        self._ctx: Context | None = None
        self._rescan = None
        self._started = False

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx

    async def enable(self) -> None:
        assert self._ctx is not None
        mm = self._ctx.use("module_manager")
        bridge = self._ctx.use("bridge")
        self._rescan = mm.rescan
        bridge.run_on_ui(self._start_watcher)   # QObject 必须在 Qt 主线程创建

    async def disable(self) -> None:
        if self._ctx is not None:
            self._ctx.use("bridge").run_on_ui(self._stop_watcher)

    # -- Qt 线程 ----------------------------------------------------------

    def _start_watcher(self) -> None:
        if self._watcher is None:
            self._watcher = ModsWatcher(paths.MODS_DIR, debounce_ms=self._debounce_ms)
        self._watcher.set_rescan(self._rescan)
        self._watcher.start()
        self._started = True

    def _stop_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        self._started = False

    @property
    def watcher(self) -> ModsWatcher | None:
        return self._watcher
