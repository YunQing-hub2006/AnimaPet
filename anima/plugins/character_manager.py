# -*- coding: utf-8 -*-
"""character_manager 插件: 角色卡服务 -- 当前角色解析、程序化切换、事件链。

服务名 ``"character_manager"``(PLAN Phase 2 第 3 项):

- ``characters()``  当前启用的角色卡(registry.characters 视图)
- ``current()``     当前角色(优先 config.mods.character, 否则第一个启用的)
- ``active_id()``   当前角色 id(无角色时 "")
- ``switch(id)``    切换角色: 校验 -> 写 config.mods.character -> 广播
  ``character.switch``(窗口订阅后完成刷新/表现) -> 窗口刷新时广播
  ``character.switched``。返回是否成功。
- ``card_model(id="")``   角色卡 Pydantic 聚合视图(Phase 3; 坏卡抛 ValueError)
- ``history_dir(id="")``  角色专属数据目录(data/characters/<id>/, 聊天历史
  按角色分目录隔离的落点; 自动创建)。

事件链(与 YingPet 一致, 行为模组/功能模组可监听联动):
``character.switch``(请求, 插件->窗口) -> 窗口刷新 -> ``character.switched``(完成)。
"""
from __future__ import annotations

import os
import re

from anima.core import Context, Plugin
from anima.events import EventNames
from anima.utils import log, paths

_log = log.get("character_manager")

_SAFE_ID = re.compile(r"[A-Za-z0-9._\-]+")


class CharacterManagerService:
    """角色卡生命周期服务(纯数据+事件, 不碰 Qt; 表现由窗口/bridge 完成)。"""

    def __init__(self) -> None:
        self._ctx: Context | None = None

    def bind(self, ctx: Context) -> None:
        self._ctx = ctx

    # -- 服务访问 ---------------------------------------------------------

    @property
    def config(self):
        return self._ctx.use("config")

    @property
    def registry(self):
        return self._ctx.use("mods")

    # -- 查询 -------------------------------------------------------------

    def characters(self):
        """当前启用的角色卡(有序)。"""
        return self.registry.characters

    def active_id(self) -> str:
        """当前角色 id: config.mods.character 优先, 否则第一个启用的, 无则 ""。"""
        cid = str(self.config.get("mods.character", "") or "")
        if cid and self.registry.character(cid):
            return cid
        if self.registry.characters:
            return next(iter(self.registry.characters))
        return ""

    def current(self):
        """当前角色对象; 无角色返回 None。"""
        return self.registry.character(self.active_id())

    # -- Phase 3: 角色卡模型 / 上下文隔离 ----------------------------------

    def card_model(self, char_id: str = ""):
        """角色卡 Pydantic 聚合视图(anima.models.CharacterCard)。

        缺省取当前角色; 角色不存在抛 ValueError, 卡文件坏抛 ValueError
        (调用方弹错误提示, 应用不崩 -- Phase 3 验收"坏 manifest 报错明确")。
        """
        cid = str(char_id or "").strip() or self.active_id()
        c = self.registry.character(cid)
        if c is None:
            raise ValueError("角色不存在: %s" % cid)
        from anima.models import load_card
        return load_card(c.dir)

    def history_dir(self, char_id: str = "") -> str:
        """角色专属数据目录: data/characters/<id>/(聊天历史/私有状态落点)。

        id 经白名单校验(防路径注入), 不合法抛 ValueError; 目录自动创建。
        聊天历史文件约定: data/characters/<id>/chat_history.json(Phase 4 接管)。
        """
        cid = str(char_id or "").strip() or self.active_id()
        if not cid or not _SAFE_ID.fullmatch(cid):
            raise ValueError("角色 id 非法: %r" % cid)
        d = os.path.join(paths.DATA_DIR, "characters", cid)
        os.makedirs(d, exist_ok=True)
        return d

    # -- 切换 -------------------------------------------------------------

    def switch(self, char_id: str) -> bool:
        """程序化切换角色(功能模组可用): 校验存在 -> 持久化 -> 广播 character.switch。"""
        c = self.registry.character(str(char_id))
        if c is None:
            _log.warning("character switch: 角色不存在 %r", char_id)
            return False
        self.config.set("mods.character", c.id)
        self.config.save()
        self._ctx.emit(EventNames.CHARACTER_SWITCH, {"character": c.id})
        return True


class CharacterManagerPlugin(Plugin):
    """角色管理插件: provide "character_manager" 服务。"""

    name = "character_manager"
    version = "1.0.0"
    dependencies = ["config", "loader"]

    def __init__(self, service: CharacterManagerService | None = None) -> None:
        self._svc = service if service is not None else CharacterManagerService()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        ctx.provide("character_manager", self._svc)

    async def enable(self) -> None:
        assert self._ctx is not None
        self._svc.bind(self._ctx)

    @property
    def service(self) -> CharacterManagerService:
        return self._svc
