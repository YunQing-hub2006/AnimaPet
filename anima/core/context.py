"""插件上下文：插件与内核交互的唯一入口，链式 API + 自动副作用追踪。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Self

from anima.core.effects import CleanupFn, EffectTracker
from anima.core.exceptions import ServiceNotFoundError

if TYPE_CHECKING:
    from anima.core.app import App
    from anima.core.bus import Handler
    from anima.core.plugin import Plugin

__all__ = ["Context"]


class Context:
    """每个插件在 ``load()`` 时独享一个 Context。

    除 ``use`` / ``use_strict`` / ``task``（按语义返回别的对象）外，所有方法返回 ``self`` 以支持链式
    调用。通过 ``on()`` / ``provide()`` 产生的订阅与注册都会被 :class:`EffectTracker` 记录，
    插件卸载时自动回滚；``config`` 是该插件在 ``app.config["plugins"]`` 下的私有切片。
    """

    app: "App"
    plugin: "Plugin"
    effects: EffectTracker
    config: dict[str, Any]

    def __init__(self, app: "App", plugin: "Plugin") -> None:
        self.app = app
        self.plugin = plugin
        self.effects = app.effects_for(plugin.name)
        plugins_cfg = app.config.get("plugins")
        if not isinstance(plugins_cfg, dict):
            # 容忍 ``{"plugins": None}``（例如从 YAML 加载到空节）等
            # 非字典配置，避免在构造 Context 时抛 AttributeError。
            plugins_cfg = {}
            app.config["plugins"] = plugins_cfg
        section = plugins_cfg.get(plugin.name)
        if not isinstance(section, dict):
            section = {}
            plugins_cfg[plugin.name] = section
        for key, default in type(plugin).config_defaults.items():
            section.setdefault(key, default)
        self.config = section

    def on(self, event: str, handler: "Handler", *, priority: int = 0) -> Self:
        """订阅事件；卸载时自动取消订阅。``priority`` 越大越先执行（v1.3）。"""
        self.effects.on(self.app.bus, event, handler, priority)
        return self

    def emit(self, event: str, data: Any = None) -> Self:
        """向总线发布事件。"""
        self.app.bus.emit(event, data)
        return self

    async def emit_and_wait(self, event: str, data: Any = None) -> None:
        """发布并等待全部协程 handler 完成（v1.3）；异常仍按 handler 隔离。"""
        await self.app.bus.emit_and_wait(event, data)

    async def emit_collect(self, event: str, data: Any = None) -> list[Any]:
        """发布并收集全部 handler 的返回值（v1.3）——见总线同名方法。"""
        return await self.app.bus.emit_collect(event, data)

    def provide(self, name: str, instance: Any, *, interface: type | None = None) -> Self:
        """注册服务；卸载时自动注销。

        ``interface`` 给出契约类型（v1.3）：不满足立刻抛 ``TypeError``。
        """
        if interface is not None and not isinstance(instance, interface):
            raise TypeError(f"服务 {name!r} 必须实现 {interface.__name__}")
        self.effects.provide(self.app.registry, name, instance)
        return self

    def use(self, name: str, default: Any = None, *, interface: type | None = None) -> Any:
        """获取其他插件提供的服务；不存在时返回 ``default``。

        传 ``interface`` 时校验类型（v1.3）：不符抛 ``ServiceNotFoundError``。
        """
        if not self.app.registry.has(name):
            return default
        return self._typed(name, self.app.registry.use(name), interface)

    def use_strict(self, name: str, *, interface: type | None = None) -> Any:
        """获取其他插件提供的服务；未注册时抛 ``ServiceNotFoundError``（v1.2）。

        新代码优先用它：取不到就在取用点暴露。``interface`` 校验同 ``use()``。
        """
        return self._typed(name, self.app.registry.use_strict(name), interface)

    def _typed(self, name: str, value: Any, interface: type | None) -> Any:
        """``interface`` 非空时校验服务类型，不符抛 ``ServiceNotFoundError``。"""
        if interface is not None and not isinstance(value, interface):
            raise ServiceNotFoundError(f"服务 {name!r} 不符合接口 {interface.__name__}")
        return value

    def on_cleanup(self, callback: CleanupFn) -> Self:
        """登记自定义清理操作，插件卸载时逆序执行。"""
        self.effects.push(callback)
        return self

    def task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """创建后台任务；插件卸载时自动取消并等待其结束。

        这是 Context 上唯一不返回 ``self`` 的方法（返回 Task 本身，
        供调用方做进一步控制）。需要运行中的事件循环，与总线的协程
        handler 调度语义一致。
        """
        task = asyncio.ensure_future(coro)
        self.effects.push_task(task)
        return task
