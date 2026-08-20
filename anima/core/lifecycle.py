"""生命周期管理器：加载/启用/禁用/卸载全流程管理，含 Kahn 拓扑排序。

状态机::

    unloaded -> loaded -> enabled -> disabled -> unloaded

其中 ``enabled`` 状态下调用 ``unload`` 会先自动 ``disable`` 再卸载；
其余任何跳跃式转换都是 :class:`LifecycleError`。
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError, RollbackError
from anima.core.plugin import Plugin

if TYPE_CHECKING:
    from anima.core.app import App

__all__ = ["LifecycleManager", "PluginState"]

#: 合法的状态字符串（也是 ``get_state`` 的返回值类型别名）。
PluginState = str

_UNLOADED = "unloaded"
_LOADED = "loaded"
_ENABLED = "enabled"
_DISABLED = "disabled"


class LifecycleManager:
    """管理一批插件的依赖排序与状态转换。"""

    def __init__(self, app: "App") -> None:
        self._app = app
        self._plugins: dict[str, Plugin] = {}
        self._states: dict[str, PluginState] = {}
        self._load_order: list[str] = []

    # -- 查询 ---------------------------------------------------------

    def get_state(self, name: str) -> PluginState:
        """返回插件当前状态；未知插件按 ``unloaded`` 处理。"""
        return self._states.get(name, _UNLOADED)

    def _require(self, name: str) -> Plugin:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise LifecycleError(f"插件未加载: {name!r}")
        return plugin

    # -- 批量流程 ---------------------------------------------------------

    async def load_all(self, plugins: list[Plugin]) -> None:
        """校验并按拓扑顺序加载全部插件。

        空列表是合法输入。重名、空 ``name``、缺失依赖、循环依赖都会在
        任何 ``load()`` 调用之前被检测出来（先排空栈再执行）。
        """
        seen: set[str] = set()
        for plugin in plugins:
            if not plugin.name:
                raise LifecycleError("插件 name 不能为空")
            if plugin.name in seen or plugin.name in self._plugins:
                raise LifecycleError(f"插件重复注册: {plugin.name!r}")
            seen.add(plugin.name)

        ordered = _topo_sort(plugins)

        for plugin in ordered:
            ctx = Context(self._app, plugin)
            self._plugins[plugin.name] = plugin
            self._states[plugin.name] = _LOADED
            self._load_order.append(plugin.name)
            await _call(plugin.load, ctx)

    async def enable_all(self) -> None:
        """按加载顺序启用全部已加载插件。"""
        for name in list(self._load_order):
            if self.get_state(name) == _LOADED:
                await self.enable(name)

    async def unload_all(self) -> None:
        """按逆加载顺序禁用并卸载全部插件，随后清空记录。"""
        for name in reversed(self._load_order):
            state = self.get_state(name)
            if state == _ENABLED:
                await self.disable(name)
            if self.get_state(name) in (_LOADED, _DISABLED):
                await self.unload(name)
        self._load_order.clear()

    # -- 单插件操作 ---------------------------------------------------------

    async def enable(self, name: str) -> None:
        """启用插件；仅 ``loaded`` / ``disabled`` 状态合法。"""
        plugin = self._require(name)
        state = self.get_state(name)
        if state not in (_LOADED, _DISABLED):
            raise LifecycleError(f"插件 {name!r} 不能从 {state} 转换到 enabled")
        await _call(plugin.enable)
        self._states[name] = _ENABLED

    async def disable(self, name: str) -> None:
        """禁用插件；仅 ``enabled`` 状态合法。"""
        plugin = self._require(name)
        if self.get_state(name) != _ENABLED:
            raise LifecycleError(f"插件 {name!r} 不能从 {self.get_state(name)} 转换到 disabled")
        await _call(plugin.disable)
        self._states[name] = _DISABLED

    async def unload(self, name: str) -> None:
        """卸载插件：回滚其全部副作用，再调用插件自定义清理。

        ``enabled`` 状态下会先自动 ``disable``。副作用回滚失败不阻止
        插件 ``unload()`` 的执行，最终统一抛 :class:`RollbackError`。
        """
        plugin = self._require(name)
        if self.get_state(name) == _ENABLED:
            await self.disable(name)
        if self.get_state(name) not in (_LOADED, _DISABLED):
            raise LifecycleError(f"插件 {name!r} 不能从 {self.get_state(name)} 转换到 unloaded")

        effects = self._app.effects_for(name)
        errors: list[BaseException] = []
        try:
            await effects.rollback()
        except RollbackError as exc:
            errors.extend(exc.errors)
        try:
            await _call(plugin.unload)
        except Exception as exc:
            errors.append(exc)

        del self._plugins[name]
        self._states[name] = _UNLOADED
        self._load_order.remove(name)
        self._app.discard_effects(name)
        if errors:
            raise RollbackError(errors)


def _topo_sort(plugins: list[Plugin]) -> list[Plugin]:
    """Kahn 拓扑排序：依赖项排在依赖方之前；有环时抛 :class:`DependencyError`。"""
    by_name = {p.name: p for p in plugins}
    indegree: dict[str, int] = {p.name: 0 for p in plugins}
    dependents: dict[str, list[str]] = {p.name: [] for p in plugins}

    for plugin in plugins:
        for dep in plugin.dependencies:
            if dep not in by_name:
                raise DependencyError(
                    f"插件 {plugin.name!r} 依赖的 {dep!r} 不在加载列表中"
                )
            indegree[plugin.name] += 1
            dependents[dep].append(plugin.name)

    queue = sorted(
        (p.name for p in plugins if indegree[p.name] == 0),
    )
    ordered: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for downstream in dependents[current]:
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)

    if len(ordered) != len(plugins):
        cyclic = sorted(name for name, deg in indegree.items() if deg > 0)
        raise DependencyError(f"检测到循环依赖，涉及插件: {', '.join(cyclic)}")
    return [by_name[name] for name in ordered]


async def _call(method: Any, *args: Any) -> None:
    """统一调用插件生命周期方法，同步 / 异步实现皆可。"""
    result = method(*args)
    if inspect.isawaitable(result):
        await result
