# -*- coding: utf-8 -*-
"""LLM 适配器(PLAN Phase 4): 抽象接口 + OpenAI 兼容实现。"""
from anima.adapters.base import LLMProvider, LLMReply
from anima.adapters.openai_compat import OpenAICompatProvider, build_json_suffix, parse_llm_reply

__all__ = ["LLMProvider", "LLMReply", "OpenAICompatProvider", "build_json_suffix", "parse_llm_reply"]
