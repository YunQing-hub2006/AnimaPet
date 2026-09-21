"""Phase 3 - lifecycle.py 测试。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from anima.core.app import App
from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError, RollbackError
from anima.core.lifecycle import (
    EVENT_PLUGIN_ENABLED,
    EVENT_PLUGIN_LOADED,
    EVENT_PLUGIN_UNLOADED,
    LifecycleManager,
)
from anima.core.plugin import Plugin
from tests.test_core.conftest import RecorderPlugin, make_plugin


async def test_lifecycle_empty_plugin_list(app: App):
    """空插件列表正常处理。"""
    await app.lifecycle.load_all([])
    await app.lifecycle.enable_all()
    await app.lifecycle.unload_all()


async def test_load_single_plugin(app: App):
    """单插件正常加载启用卸载。"""
    plugin = make_plugin("solo")
    await app.lifecycle.load_all([plugin])
    assert app.lifecycle.get_state("solo") == "loaded"
    await app.lifecycle.enable("solo")
    assert app.lifecycle.get_state("solo") == "enabled"
    await app.lifecycle.disable("solo")
    assert app.lifecycle.get_state("solo") == "disabled"
    await app.lifecycle.unload("solo")
    assert app.lifecycle.get_state("solo") == "unloaded"


async def test_load_with_dependency(app: App):
    """依赖项先于依赖方加载。"""
    db = make_plugin("db")
    api = make_plugin("api", dependencies=["db"])
    await app.lifecycle.load_all([api, db])  # 故意乱序传入

    assert db.calls == ["load"]
    assert api.calls == ["load"]
    assert app.lifecycle.get_state("db") == "loaded"
    assert app.lifecycle.get_state("api") == "loaded"


async def test_topo_sort_order(app: App):
    """多层依赖的拓扑顺序：所有依赖项在依赖方之前。"""
    plugins = [
        make_plugin("app", dependencies=["auth", "db"]),
        make_plugin("auth", dependencies=["db"]),
        make_plugin("cache", dependencies=["app"]),
        make_plugin("db"),
    ]
    order: list[str] = []
    for p in plugins:
        original = p.load

        async def wrapped(ctx, _name=p.name, _orig=original):
            order.append(_name)
            await _orig(ctx)

        p.load = wrapped  # type: ignore[method-assign]

    await app.lifecycle.load_all(plugins)
    assert order.index("db") < order.index("auth")
    assert order.index("db") < order.index("app")
    assert order.index("auth") < order.index("app")
    assert order.index("app") < order.index("cache")


async def test_circular_dependency_detection(app: App):
    """循环依赖检测并抛出 DependencyError。"""
    a = make_plugin("a", dependencies=["b"])
    b = make_plugin("b", dependencies=["a"])
    with pytest.raises(DependencyError):
        await app.lifecycle.load_all([a, b])
    # 检测发生在任何 load 之前 -> 两个插件都未被加载
    assert app.lifecycle.get_state("a") == "unloaded"
    assert a.calls == []


async def test_self_circular_dependency(app: App):
    """自依赖也算循环。"""
    a = make_plugin("a", dependencies=["a"])
    with pytest.raises(DependencyError):
        await app.lifecycle.load_all([a])


async def test_missing_dependency_detection(app: App):
    """缺失依赖检测并抛出 DependencyError。"""
    a = make_plugin("a", dependencies=["ghost"])
    with pytest.raises(DependencyError):
        await app.lifecycle.load_all([a])
    assert a.calls == []


async def test_circular_dependency_error_reports_actual_cycle(app: App):
    """环报告只列真实环成员，不含仅被环拖累的下游插件。"""
    a = make_plugin("a", dependencies=["b"])
    b = make_plugin("b", dependencies=["a"])
    downstream = make_plugin("downstream", dependencies=["a"])

    # 列表顺序即 DFS 起点顺序：先走无环的 downstream，再命中真实环
    with pytest.raises(DependencyError) as info:
        await app.lifecycle.load_all([downstream, a, b])

    message = str(info.value)
    assert "a -> b -> a" in message
    # 旧实现会把 downstream 一起报成"涉及插件"，误导排查方向
    assert "downstream" not in message
    assert downstream.calls == []


async def test_circular_dependency_three_node_cycle_path(app: App):
    """三元环报告为闭合路径 a -> b -> c -> a。"""
    with pytest.raises(DependencyError) as info:
        await app.lifecycle.load_all(
            [
                make_plugin("a", dependencies=["c"]),
                make_plugin("b", dependencies=["a"]),
                make_plugin("c", dependencies=["b"]),
            ]
        )

    nodes = str(info.value).split(": ", 1)[1].split(" -> ")
    assert len(nodes) == 4
    assert nodes[0] == nodes[-1]
    assert set(nodes) == {"a", "b", "c"}


async def test_unload_all_survives_cancelled_background_task(app: App):
    """插件先自行取消了后台任务，卸载仍须继续，不得困住其他插件。"""
    unloaded: list[str] = []

    class TaskOwner(Plugin):
        name = "task-owner"

        async def load(self, ctx: Context) -> None:
            async def loop() -> None:
                await asyncio.sleep(60)

            self.task = ctx.task(loop())

    class Follower(Plugin):
        name = "follower"

        async def load(self, ctx: Context) -> None:
            ...

        async def unload(self) -> None:
            unloaded.append("follower")

    owner = TaskOwner()
    await app.start([owner, Follower()])
    await asyncio.sleep(0)

    owner.task.cancel()
    while not owner.task.done():
        await asyncio.sleep(0)

    await app.stop()  # 修复前：CancelledError 打断整条卸载链
    assert unloaded == ["follower"]
    assert app.lifecycle.get_state("follower") == "unloaded"


async def test_unload_reverses_load_order(app: App):
    """卸载按逆拓扑顺序执行。"""
    plugins = [
        make_plugin("app", dependencies=["db"]),
        make_plugin("db"),
    ]
    await app.lifecycle.load_all(plugins)
    await app.lifecycle.enable_all()

    events: list[str] = []
    for p in plugins:
        p.unload = lambda _p=p: events.append(f"unload:{_p.name}") or _noop()  # type: ignore[method-assign]
        p.disable = lambda _p=p: events.append(f"disable:{_p.name}") or _noop()  # type: ignore[method-assign]

    await app.lifecycle.unload_all()
    # db 先于 app 加载 -> app 先卸载
    assert events == ["disable:app", "unload:app", "disable:db", "unload:db"]


async def test_state_transitions(app: App):
    """状态机: unloaded -> loaded -> enabled -> disabled -> unloaded。"""
    plugin = make_plugin("sm")
    await app.lifecycle.load_all([plugin])
    await app.lifecycle.enable("sm")
    await app.lifecycle.disable("sm")
    await app.lifecycle.enable("sm")  # disabled -> enabled 合法
    await app.lifecycle.disable("sm")
    await app.lifecycle.unload("sm")
    assert app.lifecycle.get_state("sm") == "unloaded"


async def test_invalid_state_transition_raises(app: App):
    """非法转换抛 LifecycleError。"""
    plugin = make_plugin("inv")
    await app.lifecycle.load_all([plugin])

    # loaded -> unloaded 合法；但 loaded -> disable 非法
    with pytest.raises(LifecycleError):
        await app.lifecycle.disable("inv")

    await app.lifecycle.enable("inv")
    # enabled -> unload 自动 disable，所以这里测 enable -> enable 非法
    with pytest.raises(LifecycleError):
        await app.lifecycle.enable("inv")

    await app.lifecycle.unload("inv")
    # unloaded 状态下一切操作都非法
    with pytest.raises(LifecycleError):
        await app.lifecycle.enable("inv")
    with pytest.raises(LifecycleError):
        await app.lifecycle.disable("inv")
    with pytest.raises(LifecycleError):
        await app.lifecycle.unload("inv")


async def test_unload_unknown_plugin_raises(app: App):
    """对未知插件操作抛 LifecycleError。"""
    with pytest.raises(LifecycleError):
        await app.lifecycle.enable("ghost")
    with pytest.raises(LifecycleError):
        await app.lifecycle.disable("ghost")
    with pytest.raises(LifecycleError):
        await app.lifecycle.unload("ghost")


async def test_load_empty_name_raises(app: App):
    """空 name 插件抛 LifecycleError。"""
    with pytest.raises(LifecycleError):
        await app.lifecycle.load_all([make_plugin("")])


async def test_duplicate_plugin_name_raises(app: App):
    """重名插件抛 LifecycleError。"""
    with pytest.raises(LifecycleError):
        await app.lifecycle.load_all([make_plugin("dup"), make_plugin("dup")])


async def test_unload_cleans_effects(app: App):
    """卸载回滚插件登记的全部副作用。"""
    received: list = []

    class BusyPlugin(RecorderPlugin):
        async def load(self, ctx: Context) -> None:
            await super().load(ctx)
            ctx.on("tick", lambda d: received.append(d))
            ctx.provide("svc", 42)

    busy = BusyPlugin("busy")
    await app.start([busy])
    assert app.bus.count() == 1
    assert app.registry.has("svc")

    await app.stop()
    assert app.bus.count() == 0
    assert not app.registry.has("svc")
    app.bus.emit("tick", 1)
    assert received == []


async def test_unload_enabled_plugin_auto_disables():
    """enabled 状态下 unload 先自动 disable。"""
    app = App()
    plugin = make_plugin("auto")
    await app.start([plugin])
    await app.lifecycle.unload("auto")
    assert plugin.calls == ["load", "enable", "disable", "unload"]


async def test_rollback_error_propagates_from_unload():
    """cleanup 失败时 unload 统一抛 RollbackError，插件仍被移除。"""
    app = App()
    plugin = make_plugin("broken")
    await app.start([plugin])

    def bad_cleanup():
        raise RuntimeError("清理失败")

    app.effects_for("broken").push(bad_cleanup)

    with pytest.raises(RollbackError):
        await app.lifecycle.unload("broken")

    # 插件状态仍然是 unloaded（尽力而为的清理语义）
    assert app.lifecycle.get_state("broken") == "unloaded"


async def test_load_all_after_unload_same_plugin():
    """卸载后的插件可以重新加载（状态不泄漏）。"""
    app = App()
    plugin = make_plugin("recycle")
    await app.start([plugin])
    await app.stop()

    plugin2 = make_plugin("recycle")
    await app.start([plugin2])
    assert app.lifecycle.get_state("recycle") == "enabled"


async def test_get_state_unknown_is_unloaded(app: App):
    """未知插件状态按 unloaded 处理。"""
    assert app.lifecycle.get_state("never-seen") == "unloaded"


def test_manager_constructs_with_app(app: App):
    """LifecycleManager(app) 可直接构造。"""
    manager = LifecycleManager(app)
    assert manager.get_state("x") == "unloaded"


async def test_unload_all_skips_missing_entries(app: App):
    """unload_all 对中途被单独卸载的插件不重复操作。"""
    plugin = make_plugin("one")
    await app.start([plugin])
    await app.lifecycle.unload("one")
    await app.lifecycle.unload_all()  # 不抛
    assert app.lifecycle.get_state("one") == "unloaded"


# ---------- v1.1.1 批量操作原子性 ----------


class LoadFailurePlugin(RecorderPlugin):
    """load() 抛异常的插件。"""

    def __init__(self, name: str, dependencies: list[str] | None = None) -> None:
        super().__init__(name, dependencies)
        self.error: BaseException = RuntimeError(f"{name} load 失败")

    async def load(self, ctx: Any) -> None:
        raise self.error


class EnableFailurePlugin(RecorderPlugin):
    """enable() 抛异常的插件。"""

    def __init__(self, name: str, dependencies: list[str] | None = None) -> None:
        super().__init__(name, dependencies)
        self.error: BaseException = RuntimeError(f"{name} enable 失败")

    async def enable(self) -> None:
        raise self.error


async def test_load_failure_rolls_back_previous_plugins(app: App):
    """load 中途失败：已加载插件被逆序卸载，无状态残留。"""
    received: list = []

    class BusyPlugin(RecorderPlugin):
        async def load(self, ctx: Any) -> None:
            await super().load(ctx)
            ctx.on("tick", lambda d: received.append(d))
            ctx.provide("svc", 42)

    good = BusyPlugin("good")
    # 依赖 good 保证拓扑序：good 先加载，bad 的 load 再失败
    bad = LoadFailurePlugin("bad", dependencies=["good"])
    with pytest.raises(RuntimeError):
        await app.lifecycle.load_all([good, bad])

    assert app.lifecycle.get_state("good") == "unloaded"
    assert app.lifecycle.get_state("bad") == "unloaded"
    assert app.bus.count() == 0
    assert app.registry.list() == []
    assert good.calls == ["load", "unload"]

    # 半加载状态被完全清理 -> 可以重新加载
    await app.lifecycle.load_all([make_plugin("good")])
    assert app.lifecycle.get_state("good") == "loaded"


async def test_load_failure_rollback_reverse_order(app: App):
    """load 失败回滚按逆加载序：依赖方先于依赖项被卸载。"""
    events: list[str] = []
    db = make_plugin("db")
    api = make_plugin("api", dependencies=["db"])
    broken = LoadFailurePlugin("broken", dependencies=["api"])
    for p in (db, api, broken):
        original = p.unload
        p.unload = lambda _p=p, _orig=original: events.append(f"unload:{_p.name}") or _orig()  # type: ignore[method-assign]

    # 加载序 db -> api -> broken，失败后逆序卸载
    with pytest.raises(RuntimeError):
        await app.lifecycle.load_all([db, api, broken])

    assert events == ["unload:broken", "unload:api", "unload:db"]


async def test_load_failure_rollback_error_aggregates(app: App):
    """load 失败且回滚清理也失败：抛聚合 RollbackError，cause 指向原始异常。"""
    good = make_plugin("good")

    class BadCleanupPlugin(LoadFailurePlugin):
        async def load(self, ctx: Any) -> None:
            # 抛异常前登记一个会失败的 cleanup，污染回滚
            ctx.on_cleanup(_raise_cleanup_error)
            raise self.error

    bad = BadCleanupPlugin("bad", dependencies=["good"])
    with pytest.raises(RollbackError) as info:
        await app.lifecycle.load_all([good, bad])

    assert info.value.__cause__ is bad.error  # cause 指向原始 load 异常
    # errors 只装清理失败项，不含原始 load 异常
    assert [str(e) for e in info.value.errors] == ["清理失败"]
    # good 仍被卸载
    assert app.lifecycle.get_state("good") == "unloaded"


async def test_enable_failure_rolls_back_all(app: App):
    """enable 中途失败：已启用插件走 disable + unload，全部回到 unloaded。"""
    plugin = make_plugin("ok")
    # 依赖 ok 保证 ok 先启用，bad 的 enable 再失败
    bad = EnableFailurePlugin("bad", dependencies=["ok"])
    with pytest.raises(RuntimeError):
        await app.lifecycle.load_all([plugin, bad])
        await app.lifecycle.enable_all()

    assert app.lifecycle.get_state("ok") == "unloaded"
    assert app.lifecycle.get_state("bad") == "unloaded"
    assert plugin.calls == ["load", "enable", "disable", "unload"]
    # 失败后可重新加载启用
    await app.lifecycle.load_all([make_plugin("ok")])
    await app.lifecycle.enable_all()
    assert app.lifecycle.get_state("ok") == "enabled"


async def test_load_all_rollback_on_cancellation(app: App):
    """load 被取消（CancelledError）也触发回滚，不留半加载状态。"""
    good = make_plugin("good")

    class CancelledPlugin(LoadFailurePlugin):
        def __init__(self, name: str, dependencies: list[str] | None = None) -> None:
            super().__init__(name, dependencies)
            self.error = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await app.lifecycle.load_all([good, CancelledPlugin("cancel", dependencies=["good"])])

    assert app.lifecycle.get_state("good") == "unloaded"
    assert app.lifecycle.get_state("cancel") == "unloaded"


async def test_unload_all_continues_after_disable_hook_failure(app: App):
    """unload_all 中 disable 钩子抛异常：聚合上报，不阻断其余插件卸载。"""
    good = make_plugin("good")
    bad = make_plugin("bad", dependencies=["good"])

    def bad_disable() -> None:
        raise RuntimeError("disable 失败")

    bad.disable = bad_disable  # type: ignore[method-assign]

    await app.lifecycle.load_all([good, bad])
    await app.lifecycle.enable_all()

    with pytest.raises(RollbackError) as info:
        await app.lifecycle.unload_all()

    assert [str(e) for e in info.value.errors] == ["disable 失败"]
    # good 不被 bad 的失败阻断
    assert app.lifecycle.get_state("good") == "unloaded"
    # bad 的 disable 未完成，状态卡在 enabled（单插件语义不变）
    assert app.lifecycle.get_state("bad") == "enabled"


def _raise_cleanup_error():
    raise RuntimeError("清理失败")


def _noop():
    """供 lambda 排序钩子返回的空协程占位。"""
    return None


# ---------- v1.2: 单插件热插拔 load_one（P2-3） ----------


async def test_load_one_loads_and_enables(app: App):
    """load_one 把单个插件推进到 enabled，并注入 ctx。"""
    plugin = make_plugin("late")
    await app.lifecycle.load_one(plugin)

    assert app.lifecycle.get_state("late") == "enabled"
    assert plugin.calls == ["load", "enable"]
    assert plugin.ctx is not None


async def test_load_one_rejects_empty_name_and_duplicates(app: App):
    """空名与重名都在任何 load() 之前被拦下。"""
    with pytest.raises(LifecycleError):
        await app.lifecycle.load_one(make_plugin(""))

    plugin = make_plugin("dup")
    await app.lifecycle.load_one(plugin)
    with pytest.raises(LifecycleError):
        await app.lifecycle.load_one(make_plugin("dup"))


async def test_load_one_rejects_dependency_not_loaded(app: App):
    """依赖不在已加载集合里 -> DependencyError，且不执行 load()。"""
    orphan = make_plugin("orphan", dependencies=["ghost"])
    with pytest.raises(DependencyError):
        await app.lifecycle.load_one(orphan)
    assert orphan.calls == []


async def test_load_one_accepts_dependency_already_loaded(app: App):
    """热插拔插件可以依赖已经在跑的插件。"""
    await app.lifecycle.load_one(make_plugin("db"))

    api = make_plugin("api", dependencies=["db"])
    await app.lifecycle.load_one(api)
    assert app.lifecycle.get_state("api") == "enabled"


async def test_load_one_failure_rolls_back_only_new_plugin(app: App):
    """新插件 load 失败时，已在跑的插件完全不受影响。"""
    await app.lifecycle.load_one(make_plugin("running"))

    class BadLoad(Plugin):
        name = "bad"

        async def load(self, ctx: Context) -> None:
            ctx.provide("bad-svc", 1)
            raise RuntimeError("热插拔失败")

    with pytest.raises(RuntimeError):
        await app.lifecycle.load_one(BadLoad())

    assert app.lifecycle.get_state("bad") == "unloaded"
    assert app.lifecycle.get_state("running") == "enabled"
    assert app.registry.has("bad-svc") is False
    assert app.effects_for("running").count() == 0


async def test_dependents_of_lists_direct_dependents(app: App):
    """dependents_of 只报直接依赖方。"""
    await app.lifecycle.load_one(make_plugin("db"))
    assert app.lifecycle.dependents_of("db") == []

    await app.lifecycle.load_one(make_plugin("api", dependencies=["db"]))
    assert app.lifecycle.dependents_of("db") == ["api"]
    assert app.lifecycle.dependents_of("api") == []

# ---------- v1.3: 生命周期事件（P3-3） ----------


async def test_lifecycle_events_carry_plugin_name(app: App):
    """loaded / enabled / unloaded 依序发出，payload 是插件名。"""
    events: list = []
    for name in (EVENT_PLUGIN_LOADED, EVENT_PLUGIN_ENABLED, EVENT_PLUGIN_UNLOADED):
        app.bus.subscribe(name, lambda d, n=name: events.append((n, d)))

    await app.start([make_plugin("solo")])
    assert events == [
        (EVENT_PLUGIN_LOADED, "solo"),
        (EVENT_PLUGIN_ENABLED, "solo"),
    ]

    await app.stop()
    assert events[-1] == (EVENT_PLUGIN_UNLOADED, "solo")


async def test_plugin_cannot_hear_its_own_unloaded_event(app: App):
    """unloaded 在副作用回滚之后发出：卸载者自己的订阅已经没了。"""
    received: list = []

    class SelfWatcher(Plugin):
        name = "self-watcher"

        async def load(self, ctx: Context) -> None:
            ctx.on(EVENT_PLUGIN_UNLOADED, lambda d: received.append(d))

    await app.start([SelfWatcher()])
    await app.stop()

    assert received == []
    assert app.bus.count() == 0


async def test_lifecycle_events_cover_hot_plug(app: App):
    """通配订阅能看到全部生命周期事件，热插拔同样发。"""
    seen: list = []
    app.bus.subscribe("kernel.plugin.*", lambda d: seen.append(d))

    await app.start([make_plugin("resident")])
    await app.load_plugin(make_plugin("late"))
    await app.unload_plugin("late")
    await app.stop()

    assert seen == ["resident", "resident", "late", "late", "late", "resident"]

# ---------- v1.3.1: ctx 是保留属性名 ----------


async def test_plugin_with_readonly_ctx_gives_actionable_error(app: App):
    """插件自己声明只读 ctx 时要报人话——ctx 是内核保留属性名。"""

    class ReadOnlyCtx(Plugin):
        name = "readonly-ctx"

        def __init__(self) -> None:
            self._ctx = None

        @property
        def ctx(self):  # type: ignore[override]
            return self._ctx

        async def load(self, ctx: Context) -> None:
            ...

    with pytest.raises(LifecycleError, match="保留属性名"):
        await app.start([ReadOnlyCtx()])
