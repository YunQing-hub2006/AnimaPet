"""Phase 4 - 性能基准测试。

对照计划 6.1 的指标表。计时基准受机器负载影响，阈值按计划目标值
放宽一个安全系数（CI 抖动保护），并打印实测值供评审记录。
"""

from __future__ import annotations

import asyncio
import time
import tracemalloc

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.effects import EffectTracker
from anima.core.lifecycle import _topo_sort
from tests.test_core.conftest import make_plugin

# Windows CI 上 perf_counter 抖动明显，阈值 = 计划目标值 x 安全系数
SAFETY = 5.0


def _avg_us(action, repeat: int) -> float:
    """返回单次操作平均耗时（微秒）。"""
    start = time.perf_counter()
    for _ in range(repeat):
        action()
    return (time.perf_counter() - start) * 1_000_000 / repeat


def test_bench_bus_emit_avg():
    """EventBus emit 平均耗时 < 0.1ms（emit 1000 次取平均）。"""
    bus = EventBus()
    received: list = []
    bus.subscribe("evt", lambda d: received.append(d))
    avg_us = _avg_us(lambda: bus.emit("evt", 1), 1000)
    print(f"\n[bench] emit avg: {avg_us:.3f} us")
    assert avg_us < 100 * SAFETY


def test_bench_bus_emit_1000_handlers_stress():
    """压力项：1000 个 handler 订阅同一事件时单次 emit 的宽松上限。

    计划中『<0.1ms（1000 handler）』在 CPython 上不可达（每 handler
    一次函数调用已 >100ns），按压力测试口径放宽至 10ms。
    """
    bus = EventBus()
    sink = []
    for _ in range(1000):
        bus.subscribe("evt", lambda d: sink.append(d))
    start = time.perf_counter()
    bus.emit("evt", 1)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[bench] emit with 1000 handlers: {elapsed_ms:.3f} ms")
    assert elapsed_ms < 10.0
    assert len(sink) == 1000


def test_bench_topo_sort_100_plugins():
    """100 个插件拓扑排序 < 1ms。"""
    plugins = [make_plugin(f"p{i}", dependencies=[f"p{i-1}"] if i else []) for i in range(100)]
    _topo_sort(plugins)  # 预热
    start = time.perf_counter()
    order = _topo_sort(plugins)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[bench] topo sort 100 plugins: {elapsed_ms:.3f} ms")
    assert elapsed_ms < 1.0 * SAFETY
    assert len(order) == 100


async def test_bench_full_lifecycle_100_plugins():
    """100 个插件 start -> stop 全流程 < 50ms。"""
    plugins = [make_plugin(f"p{i}") for i in range(100)]
    app = App()
    await app.start(plugins[:1])  # 预热导入与代码路径
    await app.stop()

    start = time.perf_counter()
    app2 = App()
    await app2.start(plugins)
    await app2.stop()
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[bench] 100-plugin lifecycle: {elapsed_ms:.3f} ms")
    assert elapsed_ms < 50.0 * SAFETY


async def test_bench_effect_tracker_1000_rollback():
    """EffectTracker push 1000 个 noop 后 rollback < 10ms。"""
    for trial in range(3):
        tracker = EffectTracker()
        for _ in range(1000):
            tracker.push(lambda: None)
        start = time.perf_counter()
        await tracker.rollback()
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"\n[bench] rollback 1000 noops (trial {trial}): {elapsed_ms:.3f} ms")
        assert elapsed_ms < 10.0 * SAFETY


def test_bench_empty_app_memory():
    """空 App 内存占用 < 5MB（tracemalloc 峰值）。"""
    tracemalloc.start()
    app = App()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"\n[bench] empty App: current={current/1024:.1f} KiB peak={peak/1024:.1f} KiB")
    assert peak < 5 * 1024 * 1024
    assert app is not None
