"""test_core 共享 fixtures 与工具。"""

from __future__ import annotations

from typing import Any

import pytest

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.effects import EffectTracker
from anima.core.plugin import Plugin
from anima.core.registry import ServiceRegistry


class RecorderPlugin(Plugin):
    """记录生命周期调用顺序的测试插件基类。"""

    def __init__(self, name: str, dependencies: list[str] | None = None) -> None:
        self.name = name
        self.dependencies = dependencies or []
        self.calls: list[str] = []
        self.ctx: Any = None

    async def load(self, ctx: Any) -> None:
        self.calls.append("load")
        self.ctx = ctx

    async def enable(self) -> None:
        self.calls.append("enable")

    async def disable(self) -> None:
        self.calls.append("disable")

    async def unload(self) -> None:
        self.calls.append("unload")


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def registry() -> ServiceRegistry:
    return ServiceRegistry()


@pytest.fixture
def effects() -> EffectTracker:
    return EffectTracker()


@pytest.fixture
def app() -> App:
    return App()


def make_plugin(name: str, dependencies: list[str] | None = None) -> RecorderPlugin:
    return RecorderPlugin(name, dependencies)
