"""Phase 1 - plugin.py 测试。"""

from __future__ import annotations

from typing import Any

import pytest

from anima.core.context import Context
from anima.core.plugin import Plugin


class MinimalPlugin(Plugin):
    name = "minimal"

    async def load(self, ctx: Context) -> None:
        pass


class SyncLifecyclePlugin(MinimalPlugin):
    name = "sync-lifecycle"

    async def load(self, ctx: Context) -> None:  # pragma: no cover - 覆盖签名
        ...

    def enable(self) -> None:  # 同步实现
        self.enabled_flag = True

    def disable(self) -> None:
        self.enabled_flag = False

    def unload(self) -> None:
        self.unloaded_flag = True


def test_plugin_is_abstract():
    """Plugin 不能直接实例化，load 是抽象方法。"""
    with pytest.raises(TypeError):
        Plugin()  # type: ignore[abstract]

    class NoLoad(Plugin):
        pass

    with pytest.raises(TypeError):
        NoLoad()  # type: ignore[abstract]


def test_plugin_attributes():
    """默认属性与自定义属性。"""
    plugin = MinimalPlugin()
    assert plugin.name == "minimal"
    assert plugin.version == "1.0.0"
    assert plugin.dependencies == []

    class Versioned(Plugin):
        name = "versioned"
        version = "2.3.1"
        dependencies = ["db", "cache"]

        async def load(self, ctx: Context) -> None:
            ...

    v = Versioned()
    assert v.version == "2.3.1"
    assert v.dependencies == ["db", "cache"]


async def test_plugin_lifecycle_methods():
    """enable/disable/unload 默认实现是可 await 的空操作。"""
    plugin = MinimalPlugin()
    ctx: Any = None
    await plugin.load(ctx)
    await plugin.enable()
    await plugin.disable()
    await plugin.unload()


async def test_plugin_sync_lifecycle_subclass():
    """同步实现的子类同样可用（内核统一调度的契约前提）。"""
    plugin = SyncLifecyclePlugin()
    ctx: Any = None
    await plugin.load(ctx)
    # 同步方法直接调用不报错
    assert plugin.enable() is None
    assert plugin.enabled_flag is True
    plugin.disable()
    assert plugin.enabled_flag is False
    plugin.unload()
    assert plugin.unloaded_flag is True


def test_plugin_empty_dependencies_independent():
    """dependencies 为空列表时默认可独立加载。"""
    plugin = MinimalPlugin()
    assert plugin.dependencies == []
    assert isinstance(plugin, Plugin)
