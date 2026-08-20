"""Phase 1 - exceptions.py 测试。"""

from __future__ import annotations

import pytest

from anima.core.exceptions import (
    AnimaError,
    DependencyError,
    LifecycleError,
    RollbackError,
    ServiceExistsError,
    ServiceNotFoundError,
)


def test_exception_hierarchy():
    """全部内核异常都继承 AnimaError，且相互独立。"""
    for exc_type in (
        DependencyError,
        ServiceExistsError,
        ServiceNotFoundError,
        RollbackError,
        LifecycleError,
    ):
        assert issubclass(exc_type, AnimaError)
        assert issubclass(exc_type, Exception)


def test_exception_carries_message():
    """每个异常携带清晰的错误信息。"""
    cases = [
        (DependencyError("依赖缺失: 'db'"), "依赖缺失: 'db'"),
        (ServiceExistsError("服务已注册: 'cache'"), "服务已注册: 'cache'"),
        (ServiceNotFoundError("服务不存在: 'cache'"), "服务不存在: 'cache'"),
        (LifecycleError("非法状态转换"), "非法状态转换"),
    ]
    for exc, expected in cases:
        assert str(exc) == expected
        with pytest.raises(AnimaError):
            raise exc


def test_rollback_error_aggregates():
    """RollbackError 聚合多个子异常并保留引用。"""
    first = ValueError("第一个失败")
    second = RuntimeError("第二个失败")
    error = RollbackError([first, second])

    assert error.errors == [first, second]
    assert len(error.errors) == 2
    assert error.__cause__ is first
    assert "2" in str(error)
    assert "第一个失败" in str(error)
    assert "第二个失败" in str(error)


def test_rollback_error_empty_is_allowed():
    """空列表构造不抛异常（防御性边界）。"""
    error = RollbackError([])
    assert error.errors == []
    assert error.__cause__ is None


def test_rollback_error_custom_message():
    """支持自定义 message 覆盖默认摘要。"""
    original = TypeError("x")
    error = RollbackError([original], message="自定义")
    assert str(error) == "自定义"
    assert error.errors == [original]
