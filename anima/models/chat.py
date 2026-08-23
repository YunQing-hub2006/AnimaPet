# -*- coding: utf-8 -*-
"""聊天记录 Pydantic 模型(PLAN TD3: 只做导入导出边界校验)。

HistoryStore 内部仍用 dict 列表(与 YingPet 结构兼容), 本模型供:
- JSON 导入导出时整包校验(坏文件明确报错, 不写坏数据);
- 后续聊天面板/上下文管理复用消息结构。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """一条聊天消息(role/content/ts/conv)。"""

    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    ts: str = ""
    conv: int = 1


class ChatHistory(BaseModel):
    """一个角色的聊天历史整包(按角色分目录存储)。

    format=anima-chat-1 为 AnimaPet 规范格式; 旧 YingPet 平铺 list
    (无 format/conv_id) 由 HistoryStore 读取时兼容转换。
    """

    model_config = ConfigDict(extra="ignore")

    format: str = "anima-chat-1"
    character: str = ""
    conv_id: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
