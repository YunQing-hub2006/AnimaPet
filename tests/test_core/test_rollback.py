"""P4-4 - 回滚路径集成测试（从插件作者视角端到端验证）。

test_effects.py / test_lifecycle.py 覆盖的是单元语义与批量原子性；本文件
验证停止或失败时"所有副作用类型都被逆序回滚，且任何一环失败都不阻断
其余回滚"这一整体承诺。
"""

from __future__ import annotations

import asyncio

import pytest

from anima.core.app import App
from anima.core.context import Context
from anima.core.exceptions import RollbackError
from anima.core.plugin import Plugin


class FullEffectsPlugin(Plugin):
    """一次性制造全部四类副作用：服务、订阅、后台任务、自定义清理。"""

    name = "full"

    def __init__(self, order: list[str], received: list) -> None:
        self.order = order
        self.received = received
        self.task: asyncio.Task | None = None

    async def load(self, ctx: Context) -> None:
        ctx.provide("full-svc", 1)
        ctx.on("ping", lambda d: self.received.append(d))

    async def enable(self) -> None:
        async def loop() -> None:
            try:
                await asyncio.sleep(60)
            finally:
                self.order.append("task")

        self.task = self.ctx.task(loop())
        self.ctx.on_cleanup(lambda: self.order.append("cleanup"))


async def test_stop_rolls_back_every_effect_kind():
    """stop 回滚四类副作用，顺序为注册顺序的严格逆序。"""
    order: list[str] = []
    received: list = []
    app = App()
    plugin = FullEffectsPlugin(order, received)
    await app.start([plugin])

    app.bus.emit("ping", 1)
    assert received == [1]
    assert app.registry.has("full-svc") is True

    await app.stop()

    # LIFO：enable 里后登记的 cleanup 先跑，然后是后台任务
    assert order == ["cleanup", "task"]
    assert plugin.task is not None and plugin.task.cancelled()
    assert app.registry.list() == []
    assert app.bus.count() == 0

    app.bus.emit("ping", 2)  # 订阅确实没了
    assert received == [1]


async def test_background_task_cancelled_and_awaited_on_stop():
    """后台任务被 cancel 并等到真正结束（finally 执行完）。"""
    finished = asyncio.Event()

    class Worker(Plugin):
        name = "worker"

        async def load(self, ctx: Context) -> None:
            async def loop() -> None:
                try:
                    await asyncio.sleep(60)
                finally:
                    await asyncio.sleep(0)
                    finished.set()

            ctx.task(loop())

    app = App()
    await app.start([Worker()])
    await app.stop()
    assert finished.is_set()


async def test_disable_keeps_effects_until_unload():
    """disable 不回滚副作用（v1.1.2 定稿语义）：订阅与服务保留到 unload。"""
    received: list = []

    class Keep(Plugin):
        name = "keep"

        async def load(self, ctx: Context) -> None:
            ctx.provide("keep-svc", 1)
            ctx.on("ping", lambda d: received.append(d))

    app = App()
    await app.start([Keep()])
    await app.lifecycle.disable("keep")

    assert app.registry.has("keep-svc") is True
    app.bus.emit("ping", 1)
    assert received == [1]
    assert app.lifecycle.get_state("keep") == "disabled"

    await app.stop()
    assert app.registry.list() == []
    assert app.bus.count() == 0


async def test_start_failure_rolls_back_partially_registered_effects():
    """load 中途失败：该插件已登记的副作用也要回滚干净。"""
    received: list = []

    class HalfLoaded(Plugin):
        name = "half"

        async def load(self, ctx: Context) -> None:
            ctx.provide("half-svc", 1)
            ctx.on("ping", lambda d: received.append(d))
            raise RuntimeError("load 失败")

    app = App()
    with pytest.raises(RuntimeError):
        await app.start([HalfLoaded()])

    assert app.registry.list() == []
    assert app.bus.count() == 0
    assert app.lifecycle.get_state("half") == "unloaded"
    app.bus.emit("ping", 1)
    assert received == []


async def test_rollback_failure_aggregates_and_keeps_cause():
    """回滚自身的清理失败聚合为 RollbackError，cause 指向原始异常。"""
    class HalfLoaded(Plugin):
        name = "half"

        async def load(self, ctx: Context) -> None:
            ctx.provide("half-svc", 1)
            ctx.on_cleanup(lambda: (_ for _ in ()).throw(RuntimeError("清理也失败")))
            raise RuntimeError("load 失败")

    app = App()
    with pytest.raises(RollbackError) as info:
        await app.start([HalfLoaded()])

    assert isinstance(info.value.__cause__, RuntimeError)
    assert isinstance(info.value.errors[0], RuntimeError)
    # 回滚完整性：服务照样被注销
    assert app.registry.list() == []


async def test_multiple_cleanup_failures_all_collected():
    """多个 cleanup 失败全部进 errors，回滚不提前中断。"""
    order: list[str] = []

    def boom(tag: str):
        def inner() -> None:
            order.append(tag)
            raise RuntimeError(tag)

        return inner

    class Faulty(Plugin):
        name = "faulty"

        async def load(self, ctx: Context) -> None:
            ctx.on_cleanup(boom("first"))
            ctx.on_cleanup(boom("second"))
            ctx.on_cleanup(boom("third"))

    app = App()
    await app.start([Faulty()])
    with pytest.raises(RollbackError) as info:
        await app.stop()

    assert order == ["third", "second", "first"]  # 逆注册序，且一个都没漏
    assert len(info.value.errors) == 3
    assert app._started is False


async def test_failing_cleanup_does_not_block_task_cancellation():
    """自定义清理崩了，后台任务仍被取消并等待结束（回滚不中断）。"""
    cleaned: list[str] = []

    class Mixed(Plugin):
        name = "mixed"

        async def load(self, ctx: Context) -> None:
            async def loop() -> None:
                try:
                    await asyncio.sleep(60)
                finally:
                    cleaned.append("task-finally")

            ctx.task(loop())
            ctx.on_cleanup(lambda: (_ for _ in ()).throw(RuntimeError("cleanup 崩了")))

    app = App()
    await app.start([Mixed()])
    with pytest.raises(RollbackError):
        await app.stop()
    assert cleaned == ["task-finally"]


async def test_stop_continues_after_unload_hook_failure():
    """单个插件的 unload() 崩了，其余插件照常卸载且 App 可重启。"""
    unloaded: list[str] = []

    class Good(Plugin):
        name = "good"

        async def load(self, ctx: Context) -> None:
            ...

        async def unload(self) -> None:
            unloaded.append("good")

    class BadUnload(Plugin):
        name = "zz-bad"  # 名字排在 good 之后 -> 逆序卸载时先失败

        async def load(self, ctx: Context) -> None:
            ...

        async def unload(self) -> None:
            raise RuntimeError("unload 崩了")

    app = App()
    await app.start([Good(), BadUnload()])
    with pytest.raises(RollbackError) as info:
        await app.stop()

    assert unloaded == ["good"]
    assert app.lifecycle.get_state("zz-bad") == "unloaded"
    assert isinstance(info.value.errors[0], RuntimeError)

    # 失败后状态干净，可重启
    await app.start([Good()])
    assert app.lifecycle.get_state("good") == "enabled"
    await app.stop()


async def test_restart_after_failed_stop_has_clean_state():
    """stop 抛 RollbackError 之后再次 start：没有残留订阅或服务。"""

    class Faulty(Plugin):
        name = "faulty"

        async def load(self, ctx: Context) -> None:
            ctx.provide("svc", 1)
            ctx.on("ping", lambda d: None)
            ctx.on_cleanup(lambda: (_ for _ in ()).throw(RuntimeError("清理失败")))

    app = App()
    await app.start([Faulty()])
    with pytest.raises(RollbackError):
        await app.stop()

    assert app.bus.count() == 0
    assert app.registry.list() == []

    await app.start([Faulty()])
    assert app.registry.has("svc") is True  # 重新注册成功（旧名字已释放）
    with pytest.raises(RollbackError):
        await app.stop()  # 同一个插件仍然会清理失败，但状态已复位可重来
