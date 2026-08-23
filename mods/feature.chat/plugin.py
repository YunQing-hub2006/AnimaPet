# -*- coding: utf-8 -*-
"""聊天 —— 内置功能模组(方案 A)。

入口/生命周期交给 module_manager 管理; ChatFeature 是共享库
(anima/plugins/chat.py), LLM 适配器在 anima/adapters/。
"""
from anima.plugins.chat import ChatFeature


class Feature:
    id = "feature.chat"
    name = "聊天"

    def on_load(self, ctx):
        provider = ctx.data.get("provider")
        self._chat = ChatFeature(ctx, provider=provider)
        self._chat.start()

    def on_disable(self):
        chat = getattr(self, "_chat", None)
        if chat is not None:
            chat.stop()
