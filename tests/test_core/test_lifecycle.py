"""Phase 3 - lifecycle.py 测试。"""

from __future__ import annotations

import pytest

from anima.core.app import App
from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError, RollbackError
from anima.core.lifecycle import LifecycleManager
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


def _noop():
    """供 lambda 排序钩子返回的空协程占位。"""
    return None
