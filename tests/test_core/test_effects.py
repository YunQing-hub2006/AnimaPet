"""Phase 2 - effects.py 测试。"""

from __future__ import annotations

import asyncio

import pytest

from anima.core.bus import EventBus
from anima.core.effects import EffectTracker
from anima.core.exceptions import RollbackError
from anima.core.registry import ServiceRegistry


async def test_push_rollback_lifo():
    """push + rollback 成对清除，LIFO 顺序正确。"""
    tracker = EffectTracker()
    order: list[str] = []
    tracker.push(lambda: order.append("first"))
    tracker.push(lambda: order.append("second"))
    tracker.push(lambda: order.append("third"))

    assert tracker.count() == 3
    await tracker.rollback()
    assert order == ["third", "second", "first"]
    assert tracker.count() == 0


async def test_rollback_exception_survival():
    """中间 cleanup 失败不中断后续回滚，最后统一抛 RollbackError。"""
    tracker = EffectTracker()
    executed: list[str] = []

    def failing():
        raise RuntimeError("中间失败")

    tracker.push(lambda: executed.append("first"))
    tracker.push(failing)
    tracker.push(lambda: executed.append("last"))

    with pytest.raises(RollbackError):
        await tracker.rollback()

    # 失败项之前和之后的 cleanup 都执行了
    assert executed == ["last", "first"]


async def test_rollback_empty():
    """空 tracker rollback 不抛异常。"""
    tracker = EffectTracker()
    await tracker.rollback()


async def test_rollback_error_aggregation():
    """多个失败被聚合成一个 RollbackError。"""
    tracker = EffectTracker()

    def boom(tag: str):
        def inner():
            raise ValueError(tag)

        return inner

    tracker.push(boom("a"))
    tracker.push(boom("b"))
    tracker.push(boom("c"))

    with pytest.raises(RollbackError) as info:
        await tracker.rollback()

    assert len(info.value.errors) == 3
    assert [str(e) for e in info.value.errors] == ["c", "b", "a"]


def test_on_auto_unsubscribe():
    """on() 立即生效：订阅后马上能收到事件。"""
    tracker = EffectTracker()
    bus = EventBus()
    received: list = []
    handler = lambda d: received.append(d)  # noqa: E731

    tracker.on(bus, "tick", handler)
    assert tracker.count() == 1
    bus.emit("tick", 1)
    assert received == [1]


async def test_on_auto_unsubscribe_on_rollback():
    """rollback 后 on() 登记的订阅被自动取消。"""
    tracker = EffectTracker()
    bus = EventBus()
    received: list = []
    handler = lambda d: received.append(d)  # noqa: E731

    tracker.on(bus, "tick", handler)
    await tracker.rollback()
    bus.emit("tick", 99)
    assert received == []
    assert bus.count() == 0


async def test_provide_auto_unregister():
    """provide() 注册服务，rollback 自动注销。"""
    tracker = EffectTracker()
    registry = ServiceRegistry()

    tracker.provide(registry, "db", object())
    assert registry.has("db")
    await tracker.rollback()
    assert not registry.has("db")
    assert registry.list() == []


async def test_mixed_sync_async_cleanup():
    """同步与异步 cleanup 混合执行。"""
    tracker = EffectTracker()
    order: list[str] = []

    async def async_cleanup():
        order.append("async")

    tracker.push(lambda: order.append("sync-1"))
    tracker.push(async_cleanup)
    tracker.push(lambda: order.append("sync-2"))

    await tracker.rollback()
    assert order == ["sync-2", "async", "sync-1"]


async def test_async_cleanup_failure_collected():
    """异步 cleanup 抛异常也被收集。"""
    tracker = EffectTracker()

    async def boom():
        raise RuntimeError("异步失败")

    tracker.push(boom)
    with pytest.raises(RollbackError) as info:
        await tracker.rollback()
    assert len(info.value.errors) == 1


async def test_clear():
    """clear 清空栈但不执行任何 cleanup。"""
    tracker = EffectTracker()
    executed: list = []
    tracker.push(lambda: executed.append("x"))
    tracker.clear()
    assert tracker.count() == 0
    await tracker.rollback()  # 空回滚，不执行、不抛异常
    assert executed == []


def test_count():
    """count 反映栈内数量。"""
    tracker = EffectTracker()
    assert tracker.count() == 0
    tracker.push(lambda: None)
    tracker.push(lambda: None)
    assert tracker.count() == 2


# ---------- v1.1: push_task 后台任务回滚 ----------


async def test_push_task_cancels_on_rollback():
    """rollback 后登记的任务被取消。"""
    tracker = EffectTracker()
    finished = asyncio.Event()

    async def long_running():
        try:
            await asyncio.sleep(60)
        finally:
            finished.set()

    task = asyncio.ensure_future(long_running())
    tracker.push_task(task)
    assert tracker.count() == 1

    await tracker.rollback()
    assert task.cancelled()
    assert finished.is_set()
    assert tracker.count() == 0


async def test_push_task_awaits_completion():
    """rollback 等待任务真正结束（finally 执行完）而非仅发 cancel。"""
    tracker = EffectTracker()
    cleanup_done = asyncio.Event()

    async def long_running():
        try:
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(0)
            cleanup_done.set()

    task = asyncio.ensure_future(long_running())
    tracker.push_task(task)
    await tracker.rollback()
    assert cleanup_done.is_set()


async def test_push_task_exception_isolated():
    """task 抛异常不阻断其他回滚，异常进入 RollbackError 聚合。"""
    tracker = EffectTracker()
    executed: list[str] = []

    async def boom():
        raise RuntimeError("任务崩溃")

    boom_task = asyncio.ensure_future(boom())
    await asyncio.sleep(0)  # 让 boom 先抛出
    tracker.push_task(boom_task)
    tracker.push(lambda: executed.append("after"))

    with pytest.raises(RollbackError) as info:
        await tracker.rollback()
    # 其他回滚照常执行
    assert executed == ["after"]
    # task 的异常被聚合（CancelledError 之外的失败被收集）
    assert len(info.value.errors) == 1
    assert isinstance(info.value.errors[0], RuntimeError)


async def test_push_task_already_done():
    """已完成的 task 登记后 rollback 是空操作。"""
    tracker = EffectTracker()

    async def quick():
        return 42

    task = asyncio.ensure_future(quick())
    await task
    tracker.push_task(task)
    await tracker.rollback()  # 不抛异常


async def test_push_task_lifo_with_plain_push():
    """push_task 与普通 push 同栈，LIFO 顺序保持。"""
    tracker = EffectTracker()
    order: list[str] = []

    async def sleeper():
        await asyncio.sleep(60)

    task = asyncio.ensure_future(sleeper())
    tracker.push(lambda: order.append("plain-first"))
    tracker.push_task(task)
    tracker.push(lambda: order.append("plain-last"))

    await tracker.rollback()
    # 后登记的先回滚：plain-last -> task.cancel -> plain-first
    assert order == ["plain-last", "plain-first"]
    assert task.cancelled()


def test_push_task_rejects_non_task():
    """push_task 传入非 Future/Task 抛 TypeError。"""
    tracker = EffectTracker()
    with pytest.raises(TypeError):
        tracker.push_task("not-a-task")  # type: ignore[arg-type]
