"""Phase 3 - app.py 测试。"""

from __future__ import annotations

import pytest

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError, RollbackError
from anima.core.lifecycle import LifecycleManager
from anima.core.plugin import Plugin
from anima.core.registry import ServiceRegistry
from tests.test_core.conftest import make_plugin


class SenderPlugin(Plugin):
    """enable 阶段向总线发事件的插件。"""

    name = "sender"

    def __init__(self) -> None:
        self.ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self.ctx = ctx

    async def enable(self) -> None:
        assert self.ctx is not None
        self.ctx.emit("greet", "hello")


class ReceiverPlugin(Plugin):
    """load 阶段订阅事件的插件。"""

    name = "receiver"

    def __init__(self, received: list) -> None:
        self.received = received

    async def load(self, ctx: Context) -> None:
        ctx.on("greet", lambda d: self.received.append(d))


class ProviderPlugin(Plugin):
    """load 阶段提供服务的插件。"""

    name = "provider"

    async def load(self, ctx: Context) -> None:
        ctx.provide("math", 42)


class ConsumerPlugin(Plugin):
    """enable 阶段使用依赖方服务的插件。"""

    name = "consumer"
    dependencies = ["provider"]

    def __init__(self, used: list) -> None:
        self.used = used
        self.ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self.ctx = ctx

    async def enable(self) -> None:
        assert self.ctx is not None
        self.used.append(self.ctx.use("math"))


class NoisyPlugin(Plugin):
    """登记订阅 + 服务的插件，用于验证 stop 清理。"""

    name = "noisy"

    async def load(self, ctx: Context) -> None:
        ctx.on("evt", lambda d: None)
        ctx.provide("svc", object())


async def test_app_start_stop():
    """start 后全部 enabled，stop 后全部 unloaded。"""
    app = App()
    plugins = [make_plugin("a"), make_plugin("b")]
    await app.start(plugins)

    assert app.lifecycle.get_state("a") == "enabled"
    assert app.lifecycle.get_state("b") == "enabled"

    await app.stop()
    assert app.lifecycle.get_state("a") == "unloaded"
    assert app.lifecycle.get_state("b") == "unloaded"


async def test_app_plugins_interact_via_bus():
    """插件经总线通信：sender emit，receiver 收到。"""
    received: list = []
    app = App()
    await app.start([ReceiverPlugin(received), SenderPlugin()])
    assert received == ["hello"]
    await app.stop()


async def test_app_plugins_share_via_registry():
    """provider 提供服务，consumer 在 enable 阶段 use 到。"""
    used: list = []
    app = App()
    await app.start([ProviderPlugin(), ConsumerPlugin(used)])
    assert used == [42]
    await app.stop()


async def test_app_stop_cleans_all():
    """stop 后 bus 和 registry 为空。"""
    app = App()
    await app.start([NoisyPlugin()])
    assert app.bus.count() == 1
    assert app.registry.list() == ["svc"]

    await app.stop()
    assert app.bus.count() == 0
    assert app.registry.list() == []


async def test_app_restartable():
    """重复 start/stop 不泄漏状态。"""
    app = App()

    for round_no in range(3):
        await app.start([make_plugin(f"p{round_no}")])
        assert app.lifecycle.get_state(f"p{round_no}") == "enabled"
        await app.stop()
        assert app.bus.count() == 0
        assert app.registry.list() == []


async def test_app_double_start_raises():
    """运行中重复 start 抛 LifecycleError。"""
    app = App()
    await app.start([make_plugin("x")])
    with pytest.raises(LifecycleError):
        await app.start([make_plugin("y")])
    await app.stop()


async def test_app_stop_before_start_is_noop():
    """未启动时 stop 是空操作。"""
    app = App()
    await app.stop()


def test_app_init_components():
    """__init__ 创建 bus / registry / lifecycle 与 config。"""
    app = App()
    assert isinstance(app.bus, EventBus)
    assert isinstance(app.registry, ServiceRegistry)
    assert isinstance(app.lifecycle, LifecycleManager)
    assert app.lifecycle._app is app
    assert app.config == {"plugins": {}}


async def test_app_start_dependency_error_leaves_no_partial_state():
    """start 失败（循环依赖）后 App 仍可 stop（幂等）。"""
    app = App()
    a = make_plugin("a", dependencies=["b"])
    b = make_plugin("b", dependencies=["a"])
    with pytest.raises(DependencyError):
        await app.start([a, b])
    await app.stop()  # 不抛


async def test_app_start_missing_dependency_raises():
    """start 时缺失依赖抛 DependencyError。"""
    app = App()
    with pytest.raises(DependencyError):
        await app.start([make_plugin("a", dependencies=["ghost"])])


# ---------- v1.1.1 start/stop 原子性 ----------


async def test_app_start_load_failure_is_recoverable():
    """load 阶段失败：副作用被回滚，App 可再次 start 成功。"""
    app = App()

    class NoisyThenFail(Plugin):
        name = "noisy"

        async def load(self, ctx: Context) -> None:
            ctx.on("evt", lambda d: None)
            ctx.provide("svc", 1)
            raise RuntimeError("load 失败")

    with pytest.raises(RuntimeError):
        await app.start([NoisyThenFail()])

    assert app.bus.count() == 0
    assert app.registry.list() == []
    assert app.lifecycle.get_state("noisy") == "unloaded"

    # 半启动状态被清理 -> 可再次 start
    await app.start([make_plugin("fresh")])
    assert app.lifecycle.get_state("fresh") == "enabled"
    await app.stop()


async def test_app_start_enable_failure_is_recoverable():
    """enable 阶段失败：已启用插件被回滚，App 可再次 start 成功。"""
    app = App()

    class EnableFail(Plugin):
        name = "boom"

        async def load(self, ctx: Context) -> None:
            ctx.provide("svc", 1)

        async def enable(self) -> None:
            raise RuntimeError("enable 失败")

    good = make_plugin("good")
    with pytest.raises(RuntimeError):
        await app.start([good, EnableFail()])

    assert app.bus.count() == 0
    assert app.registry.list() == []
    assert app.lifecycle.get_state("good") == "unloaded"
    assert app.lifecycle.get_state("boom") == "unloaded"

    await app.start([make_plugin("fresh")])
    assert app.lifecycle.get_state("fresh") == "enabled"
    await app.stop()


async def test_unload_all_continues_after_cleanup_failure():
    """unload_all 中单个插件清理失败不阻断其余卸载，stop 仍复位状态。"""
    app = App()

    class FaultyCleanup(Plugin):
        name = "faulty"

        async def load(self, ctx: Context) -> None:
            ctx.on_cleanup(lambda: (_ for _ in ()).throw(RuntimeError("清理失败")))

    good = make_plugin("good")
    await app.start([good, FaultyCleanup()])

    with pytest.raises(RollbackError):
        await app.stop()

    # good 不被 faulty 的失败阻断
    assert app.lifecycle.get_state("good") == "unloaded"
    assert app.lifecycle.get_state("faulty") == "unloaded"
    # stop 兜底清理仍执行，App 可重启
    assert app.bus.count() == 0
    assert app.registry.list() == []
    assert app._started is False
    await app.start([make_plugin("next")])
    await app.stop()


# ---------- v1.2: 单插件热插拔（P2-3） ----------


class HotService(Plugin):
    """热插拔用的最小服务提供者。"""

    name = "hot"

    async def load(self, ctx: Context) -> None:
        ctx.provide("hot-svc", "ready")


async def test_app_hot_plug_requires_started_app():
    """未 start 时热插拔被拒绝（先 start 再装卸单个插件）。"""
    app = App()
    with pytest.raises(LifecycleError):
        await app.load_plugin(make_plugin("late"))
    with pytest.raises(LifecycleError):
        await app.unload_plugin("late")


async def test_app_hot_plug_roundtrip():
    """运行中装卸单个插件：服务随装随卸，其余插件不受影响。"""
    app = App()
    await app.start([make_plugin("resident")])

    await app.load_plugin(HotService())
    assert app.lifecycle.get_state("hot") == "enabled"
    assert app.registry.use("hot-svc") == "ready"

    await app.unload_plugin("hot")
    assert app.lifecycle.get_state("hot") == "unloaded"
    assert app.registry.has("hot-svc") is False
    assert app.lifecycle.get_state("resident") == "enabled"
    assert app._started is True

    await app.stop()


async def test_app_unload_plugin_refuses_when_depended_on():
    """有插件依赖时拒绝卸载，避免留下指向已消失服务的破洞插件。"""
    app = App()
    await app.start([HotService()])
    await app.load_plugin(make_plugin("consumer", dependencies=["hot"]))

    with pytest.raises(LifecycleError):
        await app.unload_plugin("hot")

    await app.unload_plugin("consumer")
    await app.unload_plugin("hot")
    assert app.lifecycle.get_state("hot") == "unloaded"
    await app.stop()


async def test_app_hot_plug_failure_leaves_app_healthy():
    """热插拔失败不破坏正在运行的 App。"""
    app = App()
    await app.start([make_plugin("resident")])

    class BadLoad(Plugin):
        name = "bad"

        async def load(self, ctx: Context) -> None:
            raise RuntimeError("热插拔失败")

    with pytest.raises(RuntimeError):
        await app.load_plugin(BadLoad())

    assert app.lifecycle.get_state("bad") == "unloaded"
    assert app.lifecycle.get_state("resident") == "enabled"
    assert app._started is True
    await app.stop()


async def test_app_unload_plugin_unknown_name_raises():
    """卸载未加载的插件抛 LifecycleError（生命周期层的 require 语义）。"""
    app = App()
    await app.start([make_plugin("resident")])
    with pytest.raises(LifecycleError):
        await app.unload_plugin("ghost")
    await app.stop()
