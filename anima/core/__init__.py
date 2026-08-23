"""Anima 内核公共 API。

内核回答三个问题：插件怎么活（load/enable）、怎么死（disable/unload +
副作用自动回滚）、怎么通信（事件总线 + 服务注册表）。

.. code-block:: python

    from anima.core import App, Plugin

    class Hello(Plugin):
        name = "hello"

        async def load(self, ctx):
            ctx.provide("greeting", "hi").on("tick", lambda d: print(d))

    app = App()
    await app.start([Hello()])
    await app.stop()
"""

from anima.core.app import App
from anima.core.bus import EventBus
from anima.core.context import Context
from anima.core.effects import CleanupFn, EffectTracker
from anima.core.exceptions import (
    AnimaError,
    DependencyError,
    LifecycleError,
    RollbackError,
    ServiceExistsError,
    ServiceNotFoundError,
)
from anima.core.lifecycle import LifecycleManager, PluginState
from anima.core.plugin import Plugin
from anima.core.registry import ServiceRegistry

__all__ = [
    "AnimaError",
    "App",
    "CleanupFn",
    "Context",
    "DependencyError",
    "EffectTracker",
    "EventBus",
    "LifecycleError",
    "LifecycleManager",
    "Plugin",
    "PluginState",
    "RollbackError",
    "ServiceExistsError",
    "ServiceNotFoundError",
    "ServiceRegistry",
]

__version__ = "1.1.1"
