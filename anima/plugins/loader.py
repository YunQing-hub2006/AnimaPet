# -*- coding: utf-8 -*-
"""loader 插件: mods/ 扫描、enabled 分流、注册表服务。

服务名 ``"mods"``。加载时扫描 mods/ 并按 config.mods.enabled 分流收纳
到 Registry；``rescan()`` 供 module_manager/热重载重建。feature 型模组
的 Python 代码加载由 module_manager 负责（本插件只做数据层）。
"""
from __future__ import annotations

from anima.core import Plugin, Context
from anima.events import EventNames
from anima.mods import loader as mods_loader
from anima.mods.registry import Registry
from anima.utils import log

_log = log.get("loader")


class LoaderPlugin(Plugin):
    """模组加载插件: 扫描 -> 分流 -> provide("mods")。"""

    name = "loader"
    version = "1.0.0"
    dependencies = ["config"]

    def __init__(self) -> None:
        self._registry = Registry()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        ctx.provide("mods", self._registry)
        self.scan()

    async def enable(self) -> None:
        # 首次扫描在 load 已做; enable 阶段 config 服务必定就绪, 再按最新开关分流一次
        self.scan()

    @property
    def registry(self) -> Registry:
        return self._registry

    def scan(self) -> tuple[int, list]:
        """扫描 mods/ 并按 config.mods.enabled 分流收纳。返回 (模组数, errors)。"""
        enabled = self._enabled_map()
        mods, errors = mods_loader.scan_mods()
        self._registry.apply(mods, enabled, errors)
        n = len(mods)
        _log.info("mods scanned: %d objects, %d errors", n, len(errors))
        return n, errors

    def rescan(self) -> tuple[int, list]:
        """重扫并广播 mods.reloaded（管理器/热重载用）。"""
        result = self.scan()
        if self._ctx:
            self._ctx.emit(EventNames.MODS_RELOADED, {"errors": result[1]})
        return result

    def _enabled_map(self):
        if not self._ctx:
            return None
        cfg = self._ctx.use("config")
        if cfg is None:
            return None
        return cfg.get("mods.enabled")
