"""App：内核的唯一对外入口，组装总线、注册表与生命周期管理器。"""

from __future__ import annotations

from typing import Any

from anima.core.bus import EventBus
from anima.core.effects import EffectTracker
from anima.core.exceptions import LifecycleError
from anima.core.lifecycle import LifecycleManager
from anima.core.plugin import Plugin
from anima.core.registry import ServiceRegistry

__all__ = ["App"]


class App:
    """组装内核全部组件并驱动插件生命周期。

    用法::

        app = App()
        await app.start([MyPlugin()])
        ...
        await app.stop()
    """

    def __init__(self) -> None:
        self.bus = EventBus()
        self.registry = ServiceRegistry()
        self.config: dict[str, Any] = {"plugins": {}}
        self._effects: dict[str, EffectTracker] = {}
        self.lifecycle = LifecycleManager(self)
        self._started = False

    # -- effects 的持有者 ---------------------------------------------------------

    def effects_for(self, plugin_name: str) -> EffectTracker:
        """取（或创建）某插件的副作用追踪器。"""
        tracker = self._effects.get(plugin_name)
        if tracker is None:
            tracker = EffectTracker()
            self._effects[plugin_name] = tracker
        return tracker

    def discard_effects(self, plugin_name: str) -> None:
        """插件卸载完毕后丢弃其追踪器。"""
        self._effects.pop(plugin_name, None)

    # -- 启动 / 停止 ---------------------------------------------------------

    async def start(self, plugins: list[Plugin]) -> None:
        """加载并启用全部插件。重复 start 抛 :class:`LifecycleError`。

        load/enable 中途失败时，已注册插件由生命周期层按逆加载序回滚
        卸载；此处再兜底清空总线、注册表与追踪器，保证失败后 App 可
        再次 ``start``。清理失败聚合进 :class:`RollbackError`（cause
        指向原始异常），否则原样抛出。
        """
        if self._started:
            raise LifecycleError("App 已启动，不能重复 start")
        try:
            await self.lifecycle.load_all(plugins)
            await self.lifecycle.enable_all()
        except BaseException:
            self.bus.clear()
            self.registry.clear()
            self._effects.clear()
            raise
        self._started = True

    async def stop(self) -> None:
        """卸载全部插件并清空总线与注册表。

        未启动时调用是空操作；stop 后可以再次 ``start``（不泄漏状态）。
        单个插件的清理失败聚合为 :class:`RollbackError` 抛出，但不影响
        其余插件卸载，也不影响总线/注册表清空与 ``_started`` 复位
        （App 始终可重启）。
        """
        if not self._started:
            return
        try:
            await self.lifecycle.unload_all()
        finally:
            self.bus.clear()
            self.registry.clear()
            self._effects.clear()
            self._started = False
