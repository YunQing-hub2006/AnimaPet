# -*- coding: utf-8 -*-
"""actions 插件: 动作注册中心 + 内置动作。

服务名 ``"actions"``。规则引擎的 then 动作经此查找执行:
``get(name) -> callable(value, ctx, full_action)``。
谁提供能力谁注册 -- bridge 注册 say/emote/anim, 本插件注册
state_inc/state_set/emit, 功能模组也可注册自己的动作。
"""
from __future__ import annotations

from typing import Any, Callable

from anima.core import Plugin, Context
from anima.utils import log

_log = log.get("actions")


class ActionRegistry:
    """动作注册表: 注册-查找机制, 同名覆盖(后注册者生效)。"""

    def __init__(self) -> None:
        self._actions: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        """注册动作。fn(value, ctx, full_action)。"""
        self._actions[str(name)] = fn

    def unregister(self, name: str) -> None:
        self._actions.pop(str(name), None)

    def get(self, name: str) -> Callable | None:
        return self._actions.get(name)

    def names(self) -> list[str]:
        return sorted(self._actions)


class ActionsPlugin(Plugin):
    """动作注册中心插件: load 时 provide 注册表并登记内置动作。

    内置动作(参考 YingPet harness._register_builtin_actions):
    - ``state_inc``: {key, delta} -> state 服务自增
    - ``state_set``: {key, value} -> state 服务赋值
    - ``emit``:      {event, data} -> 总线发事件
    """

    name = "actions"
    version = "1.0.0"
    dependencies = ["state"]

    def __init__(self) -> None:
        self._reg = ActionRegistry()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        ctx.provide("actions", self._reg)

    async def enable(self) -> None:
        """依赖就绪后登记内置动作(需要 state 服务, 不能在 load 阶段 use)。"""
        assert self._ctx is not None
        state = self._ctx.use("state")

        def _state_inc(value, _ctx, _full):
            key = value.get("key", "")
            delta = value.get("delta", 1)
            if key:
                state.inc(key, delta)

        def _state_set(value, _ctx, _full):
            key = value.get("key", "")
            if key:
                state.change(key, value.get("value"))

        def _emit(value, _ctx, _full):
            event = value.get("event", "")
            if event:
                self._ctx.emit(event, value.get("data"))

        self._reg.register("state_inc", _state_inc)
        self._reg.register("state_set", _state_set)
        self._reg.register("emit", _emit)

    async def disable(self) -> None:
        """禁用时移除内置动作(bridge 等注册的动作由各自生命周期管理)。"""
        for name in ("state_inc", "state_set", "emit"):
            self._reg.unregister(name)

    @property
    def registry(self) -> ActionRegistry:
        return self._reg
