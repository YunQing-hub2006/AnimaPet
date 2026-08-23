# -*- coding: utf-8 -*-
"""LLM 适配器抽象(PLAN TD5): async chat + Reply 结果结构。

适配器只做网络/解析/降级, 不碰 UI/历史; 调用方(chat 插件)负责面板与持久化。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMReply:
    """一次 LLM 调用的结构化结果。

    ok=False 表示降级/错误回复(插件会以系统提示展示, 不写入历史)。
    """
    emotion: str = "default"
    text: str = ""
    ok: bool = True
    error: str = ""


class LLMProvider(ABC):
    """LLM 提供方抽象: 实现方必须给出 async chat()。"""

    @abstractmethod
    async def chat(self, messages: list[dict], config: dict[str, Any],
                   valid_emotions: set[str] | None = None) -> LLMReply:
        """带上下文的对话请求。

        messages: [{"role": "user"/"assistant", "content": str}, ...],
        config: api.* 配置 dict, valid_emotions: 可用表情 id 白名单。
        任何异常/坏输入都应在内部处理成 LLMReply(ok=False), 不向调用方抛网络错误。
        """
        raise NotImplementedError
