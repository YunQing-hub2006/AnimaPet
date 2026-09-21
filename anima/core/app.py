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

    # -- 单插件热插拔（v1.2） ---------------------------------------------------------

    async def load_plugin(self, plugin: Plugin) -> None:
        """运行时加载并启用**单个**插件（热插拔，v1.2）。

        要求 App 已 :meth:`start`；新插件的依赖只能指向**已经加载**的插件。
        校验（空名、重名、依赖缺失）在任何 ``plugin.load()`` 之前完成，
        失败时只回滚这一个插件——已经在跑的插件不受影响。

        注意这是"新增后启用"，不是"重新启用"：重复加载同名插件抛
        :class:`LifecycleError`。重启单个已卸载插件需要新实例。
        """
        if not self._started:
            raise LifecycleError("App 未启动，不能加载单个插件")
        await self.lifecycle.load_one(plugin)

    async def unload_plugin(self, name: str) -> None:
        """运行时卸载**单个**插件（热插拔，v1.2）。

        若仍有已加载插件依赖它，抛 :class:`LifecycleError`——先卸依赖方。
        直接放行会留下"服务已被注销、插件还在跑"的破洞状态，正是内核
        一贯要避免的中间态。
        """
        if not self._started:
            raise LifecycleError("App 未启动，不能卸载单个插件")
        dependents = self.lifecycle.dependents_of(name)
        if dependents:
            raise LifecycleError(
                f"插件 {name!r} 仍被依赖，无法卸载: {', '.join(dependents)}"
            )
        await self.lifecycle.unload(name)

    # -- 启动 / 停止 ---------------------------------------------------------

    async def start(self, plugins: list[Plugin]) -> None:
        """加载并启用全部插件；重复 start 抛 :class:`LifecycleError`。

        中途失败时先按逆加载序回滚已注册插件，再兜底清空总线/注册表/追踪器，
        保证失败后可再次 start（回滚自身的清理失败聚合为 RollbackError）。
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
        """卸载全部插件并清空总线与注册表；未启动时是空操作。

        单插件清理失败聚合为 RollbackError 抛出，但不影响其余插件卸载，也不
        影响清空与 _started 复位——App 始终可重启。
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
