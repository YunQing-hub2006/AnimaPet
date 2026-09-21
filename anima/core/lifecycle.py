"""生命周期管理器：加载/启用/禁用/卸载全流程管理，含 Kahn 拓扑排序。

状态机：``unloaded -> loaded -> enabled -> disabled -> unloaded``；
``enabled`` 下 ``unload`` 先自动 ``disable``，其余跳跃式转换抛 :class:`LifecycleError`。
"""

from __future__ import annotations

import inspect
from collections import deque
from typing import TYPE_CHECKING

from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError, RollbackError
from anima.core.plugin import Plugin

if TYPE_CHECKING:
    from anima.core.app import App

__all__ = [
    "EVENT_PLUGIN_ENABLED",
    "EVENT_PLUGIN_LOADED",
    "EVENT_PLUGIN_UNLOADED",
    "LifecycleManager",
    "PluginState",
]

#: 合法的状态字符串（也是 ``get_state`` 的返回值类型别名）。
PluginState = str

#: 生命周期事件名（v1.3）；payload 是插件名，插件可用 ``ctx.on`` 订阅做横向协作。
EVENT_PLUGIN_LOADED = "kernel.plugin.loaded"
EVENT_PLUGIN_ENABLED = "kernel.plugin.enabled"
#: 在副作用回滚之后发出——卸载中的插件自己订阅不到了。
EVENT_PLUGIN_UNLOADED = "kernel.plugin.unloaded"

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

    def dependents_of(self, name: str) -> list[str]:
        """返回当前已加载插件中直接依赖 `name` 的名字（v1.2，热插拔用）。"""
        return [other.name for other in self._plugins.values() if name in other.dependencies]

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

        某个 ``load()`` 抛异常时，已注册的全部插件（含失败者自身）按
        逆加载序尽力卸载，不留半加载状态；回滚自身的清理失败聚合进
        :class:`RollbackError`（``__cause__`` 指向原始异常）后抛出，
        否则原样重抛原始异常。
        """
        seen: set[str] = set()
        for plugin in plugins:
            if not plugin.name:
                raise LifecycleError("插件 name 不能为空")
            if plugin.name in seen or plugin.name in self._plugins:
                raise LifecycleError(f"插件重复注册: {plugin.name!r}")
            seen.add(plugin.name)

        ordered = _topo_sort(plugins)

        try:
            for plugin in ordered:
                ctx = Context(self._app, plugin)
                _inject_ctx(plugin, ctx)  # v1.2：生命周期全阶段可用的注入
                self._plugins[plugin.name] = plugin
                self._states[plugin.name] = _LOADED
                self._load_order.append(plugin.name)
                await _call(plugin.load, ctx)
                self._app.bus.emit(EVENT_PLUGIN_LOADED, plugin.name)
        except BaseException as exc:
            await self._raise_with_rollback_errors(exc)

    async def enable_all(self) -> None:
        """按加载顺序启用全部已加载插件。

        某个 ``enable()`` 抛异常时，全部插件按逆加载序卸载（已启用的
        先自动 disable），不留半启用状态；异常语义同 :meth:`load_all`。
        """
        try:
            for name in list(self._load_order):
                if self.get_state(name) == _LOADED:
                    await self.enable(name)
        except BaseException as exc:
            await self._raise_with_rollback_errors(exc)

    async def unload_all(self) -> None:
        """按逆加载顺序禁用并卸载全部插件，随后清空记录。

        单个插件的清理失败（:class:`RollbackError`）被聚合而不中断
        其余卸载；全部处理完后统一抛出。
        """
        errors = await self._unload_everything()
        self._load_order.clear()
        if errors:
            raise RollbackError(errors)

    async def _unload_everything(self) -> list[BaseException]:
        """按逆加载序尽力卸载全部插件，返回期间收集的全部异常。"""
        errors: list[BaseException] = []
        for name in reversed(list(self._load_order)):
            try:
                await self.unload(name)
            except RollbackError as exc:
                errors.extend(exc.errors)
            except Exception as exc:
                errors.append(exc)
        return errors

    async def _raise_with_rollback_errors(self, exc: BaseException) -> None:
        """load/enable 钩子失败后的统一出口：尽力卸载全部已注册插件。

        回滚自身有清理失败时抛聚合 :class:`RollbackError`（``__cause__``
        指向原始异常），否则重抛原始异常。
        """
        errors = await self._unload_everything()
        if errors:
            raise RollbackError(errors) from exc
        raise exc

    # -- 单插件操作 ---------------------------------------------------------

    async def load_one(self, plugin: Plugin) -> None:
        """运行时加载并启用**单个**插件（热插拔，v1.2）。

        与 :meth:`load_all` 的两点不同：

        - 依赖只需指向**已经加载**的插件，不必同批传入；
        - 失败回滚只回滚这一个插件，已经在跑的插件完全不受影响。

        校验（空名、重名、依赖缺失）仍然在任何 `plugin.load()` 之前完成。
        失败时原始异常原样抛出；回滚自身的清理失败则聚合进
        :class:`RollbackError`（`__cause__` 指向原始异常）。
        """
        if not plugin.name:
            raise LifecycleError("插件 name 不能为空")
        if plugin.name in self._plugins:
            raise LifecycleError(f"插件重复注册: {plugin.name!r}")
        missing = [dep for dep in plugin.dependencies if dep not in self._plugins]
        if missing:
            raise DependencyError(
                f"插件 {plugin.name!r} 依赖的 {missing[0]!r} 不在已加载插件中"
            )

        ctx = Context(self._app, plugin)
        _inject_ctx(plugin, ctx)
        self._plugins[plugin.name] = plugin
        self._states[plugin.name] = _LOADED
        self._load_order.append(plugin.name)
        try:
            await _call(plugin.load, ctx)
            self._app.bus.emit(EVENT_PLUGIN_LOADED, plugin.name)
            await self.enable(plugin.name)
        except BaseException as exc:
            # 只回滚这一个插件——_raise_with_rollback_errors 会卸载全部，
            # 那对热插拔是灾难性的。
            try:
                await self.unload(plugin.name)
            except RollbackError as rollback_exc:
                raise RollbackError(rollback_exc.errors) from exc
            raise

    async def enable(self, name: str) -> None:
        """启用插件；仅 ``loaded`` / ``disabled`` 状态合法。"""
        plugin = self._require(name)
        state = self.get_state(name)
        if state not in (_LOADED, _DISABLED):
            raise LifecycleError(f"插件 {name!r} 不能从 {state} 转换到 enabled")
        await _call(plugin.enable)
        self._states[name] = _ENABLED
        self._app.bus.emit(EVENT_PLUGIN_ENABLED, name)

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
        # 放在副作用回滚之后：卸载者自己的订阅此时已经没了。
        self._app.bus.emit(EVENT_PLUGIN_UNLOADED, name)
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

    # deque 而非 list：入队/出队是 Kahn 的高频操作，list.pop(0) 是 O(n)。
    queue: deque[str] = deque(sorted(p.name for p in plugins if indegree[p.name] == 0))
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for downstream in dependents[current]:
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)

    if len(ordered) != len(plugins):
        # 剩余节点 = 环成员 + 仅被环拖累的下游节点。直接列举它们会把
        # 无关插件报成环成员、误导排查方向，因此回溯出真实环路。
        cycle = _find_cycle(dependents)
        raise DependencyError(f"检测到循环依赖: {' -> '.join(cycle)}")
    return [by_name[name] for name in ordered]


def _find_cycle(dependents: dict[str, list[str]]) -> list[str]:
    """回溯依赖图中的一个真实环路，返回首尾闭合的路径（如 ``a -> b -> a``）。

    三色标记 DFS：命中灰色节点说明走到了当前搜索路径上的节点，从该节点
    截断即得环路。该方法只在 :func:`_topo_sort` 判定"存在环"之后调用，
    此时图中必有环；末行返回空列表仅为类型完备。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(dependents, WHITE)
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for downstream in dependents[node]:
            if color[downstream] == GRAY:
                return [*path[path.index(downstream) :], downstream]
            if color[downstream] == WHITE:
                found = visit(downstream)
                if found is not None:
                    return found
        path.pop()
        color[node] = BLACK
        return None

    for name in dependents:
        if color[name] == WHITE:
            found = visit(name)
            if found is not None:
                return found
    return []  # pragma: no cover - 调用方已保证存在环路


def _inject_ctx(plugin: Plugin, ctx: Context) -> None:
    """注入 ``plugin.ctx``；插件自己声明了只读 ``ctx`` 时给出可操作报错（v1.3.1）。"""
    try:
        plugin.ctx = ctx
    except AttributeError as exc:
        raise LifecycleError(f"插件 {plugin.name!r} 的 ctx 不可写：ctx 是内核保留属性名") from exc


async def _call(method: Any, *args: Any) -> None:
    """统一调用插件生命周期方法，同步 / 异步实现皆可。"""
    result = method(*args)
    if inspect.isawaitable(result):
        await result
