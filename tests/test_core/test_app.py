"""Phase 3 - app.py 测试。"""

from __future__ import annotations

import pytest

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.context import Context
from anima.core.exceptions import DependencyError, LifecycleError
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
