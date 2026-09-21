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
    assert plugin.dependencies == ()

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
    """dependencies 为空时默认可独立加载。"""
    plugin = MinimalPlugin()
    assert plugin.dependencies == ()
    assert isinstance(plugin, Plugin)


def test_dependencies_default_is_immutable_and_unshared():
    """默认 dependencies 是不可变元组：没有"所有子类共享一个列表"的坑。"""
    assert Plugin.dependencies == ()
    assert isinstance(Plugin.dependencies, tuple)

    # 旧实现（list 默认值）下这里会污染所有插件的类属性
    with pytest.raises(AttributeError):
        Plugin.dependencies.append("x")  # type: ignore[attr-defined]

    class Sibling(Plugin):
        name = "sibling"

        async def load(self, ctx: Context) -> None:
            ...

    assert Sibling.dependencies == ()
    assert Plugin.dependencies == ()


# ---------- v1.2: ctx 注入（P2-1） ----------


async def test_plugin_ctx_injected_for_all_phases():
    """框架在 load 之前注入 self.ctx，enable/disable/unload 都能直接用。"""
    from anima.core.app import App

    seen: list = []

    class Consumer(Plugin):
        name = "consumer"

        async def load(self, ctx: Context) -> None:
            assert self.ctx is ctx

        async def enable(self) -> None:
            seen.append(self.ctx)

        async def disable(self) -> None:
            seen.append(self.ctx)

        async def unload(self) -> None:
            seen.append(self.ctx)

    app = App()
    plugin = Consumer()
    await app.start([plugin])
    await app.stop()

    assert len(seen) == 3
    assert all(ctx is plugin.ctx for ctx in seen)


async def test_plugin_ctx_refreshed_after_restart():
    """stop 后再 start 同一实例：注入的是新的 Context。"""
    from anima.core.app import App

    plugin = MinimalPlugin()
    app = App()
    await app.start([plugin])
    first = plugin.ctx

    await app.stop()
    await app.start([plugin])
    assert plugin.ctx is not first
    await app.stop()

# ---------- v1.3: config_defaults 声明（P2-4） ----------


def test_config_defaults_is_read_only_mapping():
    """默认 config_defaults 是只读映射：子类就地写会直接报错，不会污染全局。"""
    assert dict(Plugin.config_defaults) == {}
    with pytest.raises(TypeError):
        Plugin.config_defaults["x"] = 1  # type: ignore[index]

    class WithDefaults(Plugin):
        name = "with-defaults-plugin"
        config_defaults = {"a": 1}

        async def load(self, ctx: Context) -> None:
            ...

    assert dict(WithDefaults.config_defaults) == {"a": 1}
    assert dict(Plugin.config_defaults) == {}
