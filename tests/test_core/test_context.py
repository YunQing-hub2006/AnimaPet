"""Phase 3 - context.py 测试。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from anima.core.app import App
from anima.core.context import Context
from anima.core.exceptions import ServiceNotFoundError
from anima.core.plugin import Plugin
from tests.test_core.conftest import RecorderPlugin


def _make_ctx(app: App, plugin: Plugin | None = None) -> Context:
    if plugin is None:
        plugin = RecorderPlugin("under-test")
    return Context(app, plugin)


def test_context_chain_api(app: App):
    """所有方法返回 self，支持链式调用。"""
    ctx = _make_ctx(app)
    result = (
        ctx.on("evt", lambda d: None)
        .emit("evt", 1)
        .provide("svc", object())
        .on_cleanup(lambda: None)
    )
    assert result is ctx


def test_context_config_isolation():
    """config 是各插件在 app.config['plugins'] 下的私有切片。"""
    app = App()
    ctx_a = _make_ctx(app, RecorderPlugin("plugin-a"))
    ctx_b = _make_ctx(app, RecorderPlugin("plugin-b"))

    ctx_a.config["level"] = 3
    assert ctx_b.config == {}
    assert app.config["plugins"]["plugin-a"] == {"level": 3}


def test_context_config_missing_section_gets_empty_dict():
    """配置切片缺失时自动创建空 dict。"""
    app = App()
    ctx = _make_ctx(app, RecorderPlugin("fresh"))
    assert ctx.config == {}
    assert app.config["plugins"]["fresh"] is ctx.config


def test_context_config_tolerates_none_plugins_section():
    """app.config["plugins"] 为 None（如 YAML 空节）时不崩溃。"""
    app = App()
    app.config["plugins"] = None  # type: ignore[assignment]

    ctx = _make_ctx(app, RecorderPlugin("from-none"))
    assert ctx.config == {}
    assert app.config["plugins"] == {"from-none": {}}
    assert app.config["plugins"]["from-none"] is ctx.config


def test_context_config_replaces_non_dict_section():
    """插件名下的配置切片不是 dict 时被替换为空 dict。"""
    app = App()
    app.config["plugins"]["broken"] = "not-a-dict"  # type: ignore[assignment]

    ctx = _make_ctx(app, RecorderPlugin("broken"))
    assert ctx.config == {}
    assert app.config["plugins"]["broken"] is ctx.config


def test_context_config_uses_existing_section():
    """已有配置切片被原样引用（start 前注入的配置对插件可见）。"""
    app = App()
    app.config["plugins"]["pre"] = {"key": "value"}
    ctx = _make_ctx(app, RecorderPlugin("pre"))
    assert ctx.config == {"key": "value"}


async def test_context_on_auto_cleanup(app: App):
    """on() 登记的订阅在 effects.rollback 后自动取消。"""
    ctx = _make_ctx(app, RecorderPlugin("subscriber"))
    received: list = []
    ctx.on("tick", lambda d: received.append(d))

    app.bus.emit("tick", 1)
    assert received == [1]

    await ctx.effects.rollback()
    app.bus.emit("tick", 2)
    assert received == [1]  # 不再收到


async def test_context_provide_auto_cleanup(app: App):
    """provide() 登记的服务在 effects.rollback 后自动注销。"""
    ctx = _make_ctx(app, RecorderPlugin("provider"))
    svc = object()
    ctx.provide("db", svc)

    assert ctx.use("db") is svc
    await ctx.effects.rollback()
    assert ctx.use("db") is None


def test_context_use_default(app: App):
    """use() 未找到时返回 default。"""
    ctx = _make_ctx(app)
    assert ctx.use("nope") is None
    assert ctx.use("nope", "fallback") == "fallback"


def test_context_emit_goes_to_app_bus(app: App):
    """ctx.emit 走 app 总线，其他订阅者能收到。"""
    received: list = []
    app.bus.subscribe("from-ctx", lambda d: received.append(d))
    ctx = _make_ctx(app)
    ctx.emit("from-ctx", "hello")
    assert received == ["hello"]


def test_context_attributes(app: App):
    """app / plugin / effects 属性指向正确的对象。"""
    plugin = RecorderPlugin("attrs")
    ctx = Context(app, plugin)
    assert ctx.app is app
    assert ctx.plugin is plugin
    assert ctx.effects is app.effects_for("attrs")


def test_context_effects_persist_per_plugin(app: App):
    """同一插件多次取 Context，effects 是同一个追踪器。"""
    plugin = RecorderPlugin("stable")
    ctx1 = Context(app, plugin)
    ctx2 = Context(app, plugin)
    assert ctx1.effects is ctx2.effects


async def test_context_full_lifecycle():
    """完整生命周期：load 注册副作用 -> unload 自动回滚。"""
    app = App()
    plugin = RecorderPlugin("full")
    await app.start([plugin])

    assert app.lifecycle.get_state("full") == "enabled"
    assert plugin.calls == ["load", "enable"]

    await app.stop()
    assert app.lifecycle.get_state("full") == "unloaded"
    assert plugin.calls == ["load", "enable", "disable", "unload"]
    assert app.bus.count() == 0
    assert app.registry.list() == []


async def test_context_on_cleanup_registered(app: App):
    """on_cleanup 登记的回调在卸载时执行。"""
    cleaned: list = []

    class CleanerPlugin(Plugin):
        name = "cleaner"

        async def load(self, ctx: Context) -> None:
            ctx.on_cleanup(lambda: cleaned.append("done"))

    ap = App()
    await ap.start([CleanerPlugin()])
    await ap.stop()
    assert cleaned == ["done"]


def test_context_on_cleanup_with_async(app: App):
    """on_cleanup 也接受异步回调（类型契约 CleanupFn）。"""
    ctx = _make_ctx(app)

    async def async_cleanup() -> None: ...

    ctx.on_cleanup(async_cleanup)
    assert ctx.effects.count() == 1


# ---------- v1.1: task 后台任务 ----------


async def test_context_task_returns_task(app: App):
    """ctx.task 返回 asyncio.Task 并登记回滚。"""
    ctx = _make_ctx(app, RecorderPlugin("task-owner"))

    async def work():
        return 7

    task = ctx.task(work())
    assert isinstance(task, asyncio.Task)
    assert ctx.effects.count() == 1


async def test_context_task_cancelled_on_unload(app: App):
    """插件卸载后其后台任务被取消。"""
    stopped = asyncio.Event()

    class WorkerPlugin(Plugin):
        name = "worker"

        async def load(self, ctx: Context) -> None:
            async def loop():
                try:
                    await asyncio.sleep(60)
                finally:
                    stopped.set()

            ctx.task(loop())

    await app.start([WorkerPlugin()])
    await app.stop()
    assert stopped.is_set()


def test_context_task_without_loop_raises(app: App):
    """无运行中的事件循环时 ctx.task 报 RuntimeError（与 bus 语义一致）。"""
    ctx = _make_ctx(app, RecorderPlugin("no-loop"))

    async def make():
        return None

    coro = make()
    with pytest.raises(RuntimeError):
        ctx.task(coro)
    coro.close()


# ---------- v1.2: use_strict 过渡接口（P2-2） ----------


def test_context_use_strict_raises_when_missing(app: App):
    """use_strict 未注册时抛 ServiceNotFoundError（不是返回 None）。"""
    ctx = _make_ctx(app)
    with pytest.raises(ServiceNotFoundError):
        ctx.use_strict("nope")


def test_context_use_strict_returns_service(app: App):
    """use_strict 命中时返回实例，且不影响 use 的 default 语义。"""
    ctx = _make_ctx(app, RecorderPlugin("provider"))
    ctx.provide("svc", 42)

    assert ctx.use_strict("svc") == 42
    assert ctx.use("svc") == 42
    assert ctx.use("missing") is None  # 冻结语义不变

# ---------- v1.3: config_defaults（P2-4）/ interface（P3-4）/ on priority（P3-1） ----------


class WithDefaults(Plugin):
    """声明了两个配置默认值的插件。"""

    name = "with-defaults"
    config_defaults = {"level": 3, "mode": "auto"}

    async def load(self, ctx: Context) -> None:
        ...


def test_config_defaults_fill_missing_keys(app: App):
    """config_defaults 在 load 前填进 ctx.config。"""
    ctx = _make_ctx(app, WithDefaults())
    assert ctx.config == {"level": 3, "mode": "auto"}


def test_config_defaults_do_not_override_explicit_config(app: App):
    """显式配置优先，只补缺失的 key。"""
    app.config["plugins"]["with-defaults"] = {"level": 9}
    ctx = _make_ctx(app, WithDefaults())
    assert ctx.config["level"] == 9
    assert ctx.config["mode"] == "auto"


def test_context_on_forwards_priority(app: App):
    """ctx.on 的 priority 透传到总线。"""
    ctx = _make_ctx(app, RecorderPlugin("prio"))
    calls: list[str] = []
    ctx.on("e", lambda d: calls.append("low"))
    ctx.on("e", lambda d: calls.append("high"), priority=5)

    ctx.emit("e")
    assert calls == ["high", "low"]


async def test_context_emit_collect_and_wait(app: App):
    """Context 也有 emit_collect / emit_and_wait（插件不必去碰 bus）。"""
    ctx = _make_ctx(app, RecorderPlugin("collector"))
    done: list = []

    async def handler(d):
        done.append(d)
        return "answer:" + str(d)

    ctx.on("q", handler)
    assert await ctx.emit_collect("q", 1) == ["answer:1"]
    await ctx.emit_and_wait("q", 2)
    assert done == [1, 2]


def test_provide_with_interface_accepts_match(app: App):
    """provide 的 interface 匹配时正常注册。"""
    ctx = _make_ctx(app)
    ctx.provide("counter", 5, interface=int)
    assert ctx.use("counter") == 5


def test_provide_with_interface_rejects_mismatch(app: App):
    """provide 的 interface 不匹配时抛 TypeError，且不留半注册。"""
    ctx = _make_ctx(app)
    with pytest.raises(TypeError):
        ctx.provide("counter", "5", interface=int)
    assert app.registry.has("counter") is False


def test_use_with_interface_rejects_mismatch(app: App):
    """use 的 interface 不匹配时抛 ServiceNotFoundError（视作取不到该契约的服务）。"""
    ctx = _make_ctx(app)
    app.registry.register("svc", "not-an-int")
    with pytest.raises(ServiceNotFoundError):
        ctx.use("svc", interface=int)


def test_use_with_interface_keeps_default_fallback(app: App):
    """未注册时仍返回 default，interface 不参与判断。"""
    ctx = _make_ctx(app)
    assert ctx.use("missing", "fallback", interface=int) == "fallback"


def test_use_strict_with_interface(app: App):
    """use_strict 同样支持 interface 校验。"""
    ctx = _make_ctx(app)
    app.registry.register("svc", 7)
    assert ctx.use_strict("svc", interface=int) == 7
    with pytest.raises(ServiceNotFoundError):
        ctx.use_strict("svc", interface=str)
