"""Phase 2 - registry.py 测试。"""

from __future__ import annotations

import pytest

from anima.core.exceptions import ServiceExistsError, ServiceNotFoundError
from anima.core.registry import ServiceRegistry


def test_register_use(registry: ServiceRegistry):
    """注册后 use 返回实例本身。"""
    sentinel = object()
    registry.register("db", sentinel)
    assert registry.use("db") is sentinel


def test_unregister(registry: ServiceRegistry):
    """注销后服务不可用。"""
    registry.register("db", 1)
    registry.unregister("db")
    assert not registry.has("db")
    assert registry.use("db") is None


def test_unregister_idempotent(registry: ServiceRegistry):
    """unregister 不存在的名字静默成功。"""
    registry.unregister("never-registered")  # 不抛
    registry.register("db", 1)
    registry.unregister("db")
    registry.unregister("db")  # 第二次 -> 静默


def test_duplicate_register_raises(registry: ServiceRegistry):
    """重复注册同名服务抛 ServiceExistsError。"""
    registry.register("cache", {})
    with pytest.raises(ServiceExistsError):
        registry.register("cache", {})


def test_use_default(registry: ServiceRegistry):
    """use 未注册服务返回 default。"""
    assert registry.use("missing") is None
    assert registry.use("missing", "fallback") == "fallback"
    assert registry.use("missing", 0) == 0  # falsy default 也原样返回


def test_list_services(registry: ServiceRegistry):
    """list() 返回全部服务名快照，修改快照不影响注册表。"""
    assert registry.list() == []
    registry.register("db", 1)
    registry.register("cache", 2)
    names = registry.list()
    assert sorted(names) == ["cache", "db"]
    names.clear()
    assert registry.list() == ["db", "cache"] or sorted(registry.list()) == ["cache", "db"]


def test_has(registry: ServiceRegistry):
    """has 反映注册状态。"""
    assert registry.has("db") is False
    registry.register("db", 1)
    assert registry.has("db") is True
    registry.unregister("db")
    assert registry.has("db") is False


def test_clear(registry: ServiceRegistry):
    """clear 注销全部服务。"""
    registry.register("a", 1)
    registry.register("b", 2)
    registry.clear()
    assert registry.list() == []
    assert registry.has("a") is False


# ---------- v1.2: use_strict 迁移接口（P2-2） ----------


def test_use_strict_returns_registered(registry: ServiceRegistry):
    """use_strict 命中时返回实例本身，与 use 一致。"""
    sentinel = object()
    registry.register("db", sentinel)
    assert registry.use_strict("db") is sentinel


def test_use_strict_raises_when_missing(registry: ServiceRegistry):
    """use_strict 未注册时抛 ServiceNotFoundError，而不是返回 None。"""
    with pytest.raises(ServiceNotFoundError):
        registry.use_strict("missing")


def test_use_strict_does_not_change_use_semantics(registry: ServiceRegistry):
    """use 的 default 语义是冻结的：新增 use_strict 不改它（maintenance §6）。"""
    assert registry.use("missing") is None
    assert registry.use("missing", "fallback") == "fallback"
