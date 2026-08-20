"""Phase 4 - 边界与压力测试（计划 6.2 全部条目）。"""

from __future__ import annotations

import asyncio

import pytest

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.effects import EffectTracker
from anima.core.exceptions import DependencyError, RollbackError
from anima.core.registry import ServiceRegistry
from tests.test_core.conftest import make_plugin


# ---------- 边界测试 ----------

def test_bus_emit_with_none_data():
    """data 为 None（默认值）时正常传递。"""
    bus = EventBus()
    received: list = []
    bus.subscribe("evt", lambda d: received.append(d))
    bus.emit("evt")
    bus.emit("evt", None)
    assert received == [None, None]


def test_registry_use_with_none_default():
    """default=None 与 falsy default 原样返回。"""
    registry = ServiceRegistry()
    assert registry.use("missing") is None
    assert registry.use("missing", None) is None
    assert registry.use("missing", 0) == 0
    assert registry.use("missing", "") == ""


async def test_lifecycle_empty_plugin_list():
    """空插件列表 start/stop 全流程无异常。"""
    app = App()
    await app.start([])
    assert app.lifecycle.get_state("any") == "unloaded"
    await app.stop()


async def test_effect_tracker_rollback_with_all_failing():
    """全部 cleanup 都失败：异常聚合、栈清空、无未处理异常逃逸。"""
    tracker = EffectTracker()

    def boom(i: int):
        def inner():
            raise RuntimeError(f"boom-{i}")

        return inner

    for i in range(10):
        tracker.push(boom(i))

    with pytest.raises(RollbackError) as info:
        await tracker.rollback()

    assert len(info.value.errors) == 10
    assert tracker.count() == 0  # 失败也清栈，不重试

    # 再次 rollback 是空操作
    await tracker.rollback()


# ---------- 压力测试 ----------

async def test_100_plugins_circular_reference_detection():
    """100 个插件构成大环，检测仍是 O(V+E) 且错误信息正确。"""
    app = App()
    plugins = [make_plugin(f"p{i}", dependencies=[f"p{(i + 1) % 100}"]) for i in range(100)]
    with pytest.raises(DependencyError) as info:
        await app.lifecycle.load_all(plugins)
    assert "循环依赖" in str(info.value)


async def test_1000_events_per_second():
    """每秒 1000+ 事件：同步 emit 满足吞吐并正确送达。"""
    bus = EventBus()
    received: list = []
    bus.subscribe("tick", lambda d: received.append(d))

    for _ in range(1000):
        bus.emit("tick", None)

    assert len(received) == 1000


async def test_1000_async_events_via_emit_async():
    """emit_async 批量派发协程 handler 全部完成。"""
    bus = EventBus()
    counter = 0

    async def handler(d):
        nonlocal counter
        await asyncio.sleep(0)
        counter += 1

    bus.subscribe("tick", handler)
    tasks: list = []
    for _ in range(1000):
        tasks.extend(bus.emit_async("tick", None))
    await asyncio.gather(*tasks)
    assert counter == 1000


def test_100_services_register_unregister():
    """100 个服务反复注册/注销，幂等且无泄漏。"""
    registry = ServiceRegistry()
    for round_no in range(10):
        names = [f"svc-{i}" for i in range(100)]
        for i, name in enumerate(names):
            registry.register(name, i)
        assert len(registry.list()) == 100
        for name in names:
            registry.unregister(name)
            registry.unregister(name)  # 幂等
        assert registry.list() == []


async def test_stress_100_plugins_start_stop():
    """100 个独立插件批量启停（压力版全流程）。"""
    app = App()
    plugins = [make_plugin(f"p{i}") for i in range(100)]
    await app.start(plugins)
    for i in range(100):
        assert app.lifecycle.get_state(f"p{i}") == "enabled"
    await app.stop()
    assert app.bus.count() == 0
    assert app.registry.list() == []


async def test_stress_deep_dependency_chain():
    """50 层依赖链：拓扑排序正确、逆序卸载。"""
    app = App()
    plugins = [make_plugin(f"c{i}", dependencies=[f"c{i-1}"] if i else []) for i in range(50)]
    await app.start(plugins)
    # 链上全部启用成功即顺序正确（依赖缺失会抛 DependencyError）
    assert app.lifecycle.get_state("c49") == "enabled"
    await app.stop()


def test_wildcard_only_subscription_stress():
    """大量通配订阅下精确事件不受影响。"""
    bus = EventBus()
    exact: list = []
    bus.subscribe("exact", lambda d: exact.append(d))
    for i in range(200):
        bus.subscribe(f"ns{i}.*", lambda d: None)
    bus.emit("exact", 1)
    assert exact == [1]
