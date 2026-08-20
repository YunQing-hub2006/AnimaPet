# -*- coding: utf-8 -*-
"""state 插件: 状态漏斗、state.changed 广播、持久化。

服务名 ``"state"``。change(key, value) 依次: 改内存 -> 原子落盘
state.json -> emit ``state.changed`` 事件（payload: {key, value}）。
规则引擎与桥接靠此事件实时刷新。
"""
from __future__ import annotations

from anima.core import Plugin, Context
from anima.events import EventNames
from anima.utils import jsonio, paths

#: 默认状态（首次启动的干净状态）。
DEFAULT_STATE = {
    "affinity": 0,       # 好感度
    "petted_count": 0,   # 累计摸头次数
    "last_idle": "",     # 上次随机搭话的时间戳
    "last_sit": "",      # 上次久坐提醒时间戳
    "last_night": "",    # 上次深夜提醒日期
}


class StateService:
    """状态服务: 内存 dict + 原子落盘 + change 广播。"""

    def __init__(self) -> None:
        self._data: dict = {}
        self._emit = None  # 由插件注入: emit(event, data)

    def load(self) -> dict:
        self._data = jsonio.load(paths.STATE_PATH, DEFAULT_STATE)
        return self._data

    @property
    def data(self) -> dict:
        """状态根 dict（引用共享, 读取用）。"""
        return self._data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __setitem__(self, key: str, value) -> None:
        self.change(key, value)

    def __getitem__(self, key: str):
        return self._data[key]

    def change(self, key: str, value, *, save: bool = True) -> None:
        """状态变更漏斗: 改内存 -> 落盘 -> 广播 state.changed。"""
        self._data[key] = value
        if save:
            jsonio.save(paths.STATE_PATH, self._data)
        if self._emit:
            self._emit(EventNames.STATE_CHANGED, {"key": key, "value": value})

    def inc(self, key: str, delta: int = 1, *, save: bool = True) -> None:
        """数值状态自增（不存在按 0 起算）。"""
        self.change(key, self.get(key, 0) + delta, save=save)

    def save(self) -> None:
        jsonio.save(paths.STATE_PATH, self._data)


class StatePlugin(Plugin):
    """状态服务插件: load 时加载磁盘状态并 provide, change 广播经 ctx.emit。"""

    name = "state"
    version = "1.0.0"
    dependencies = ["config"]

    def __init__(self, service: StateService | None = None) -> None:
        # main.py/集成测试可注入预建服务(与 PetWindow 共享同一实例)
        self._svc = service if service is not None else StateService()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        self._svc.load()
        self._svc._emit = ctx.emit  # 注入 emit 闭包
        ctx.provide("state", self._svc)

    async def unload(self) -> None:
        self._svc.save()
