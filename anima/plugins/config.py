# -*- coding: utf-8 -*-
"""config 插件: 配置加载、分层读取、原子保存。

服务名 ``"config"``。提供点路径 get（``get("api.model")``）与
``save()`` 原子落盘。沿用 YingPet DEFAULT_CONFIG 结构。
"""
from __future__ import annotations

from anima.core import Plugin, Context
from anima.utils import jsonio, paths

#: 默认配置（沿用 YingPet-v4 harness.DEFAULT_CONFIG）。
DEFAULT_CONFIG = {
    "api": {
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-v4-flash",
        "temperature": 0.8,
        "max_tokens": 1500,
        "timeout": 20,
        "reasoning_effort": "",
        "stream": False,   # 流式输出接口预留(Phase 4, 打字机渲染后续实现)
    },
    "window": {
        "size": "small",
        "sit_reminder": True,
        "idle_anim": "",
        "talk_anim": "",
    },
    "mods": {
        "character": "",     # 当前角色卡 id, 空 = 取第一个启用的
        "ui": "",            # 当前皮肤模组 id, 空 = 取第一个启用的
        "enabled": {},       # {mod_id: bool} 缺省视为启用
    },
    "debug": {
        "rules": False,  # true = 逐条记录规则 when/if 求值结果
    },
}


class ConfigService:
    """配置服务: 内存 dict + 原子落盘 + 点路径分层读取。"""

    def __init__(self) -> None:
        self._data: dict = {}

    def load(self) -> dict:
        """从磁盘加载配置（与 DEFAULT_CONFIG 浅合并）。"""
        self._data = jsonio.load(paths.CONFIG_PATH, DEFAULT_CONFIG)
        return self._data

    @property
    def data(self) -> dict:
        """配置根 dict（引用共享, 修改即生效, 需落盘调 save）。"""
        return self._data

    def get(self, key: str, default=None):
        """点路径分层读取: ``get("api.model")`` -> data["api"]["model"]。

        缺失任意层级返回 default。空 key 返回整个根 dict。
        """
        if not key:
            return self._data
        node: object = self._data
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, key: str, value) -> None:
        """点路径分层写入, 自动建中间 dict。"""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def save(self) -> None:
        """原子保存到 data/config.json。"""
        jsonio.save(paths.CONFIG_PATH, self._data)


class ConfigPlugin(Plugin):
    """配置服务插件: load 时加载磁盘配置并 provide。"""

    name = "config"
    version = "1.0.0"
    dependencies: list[str] = []

    def __init__(self, service: ConfigService | None = None) -> None:
        # main.py/集成测试可注入预建服务(与 PetWindow 共享同一实例)
        self._svc = service if service is not None else ConfigService()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        self._svc.load()
        ctx.provide("config", self._svc)

    async def unload(self) -> None:
        self._svc.save()
