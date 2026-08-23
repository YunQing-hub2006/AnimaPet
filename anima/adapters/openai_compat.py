# -*- coding: utf-8 -*-
"""OpenAI 兼容适配器(PLAN Phase 4 第 1 项)。

复用 YingPet-v4 feature.chat/chat_worker.py 的请求/解析/降级逻辑:
- sync requests 调用包在 asyncio.to_thread 里(阻塞网络不卡内核线程);
- 任何错误都降级为 LLMReply(ok=False), 绝不向调用方抛网络异常;
- 模型输出尽量解析 {emotion, text} JSON, 解析失败兜底纯文本。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from anima.adapters.base import LLMProvider, LLMReply
from anima.utils import log

_log = log.get("adapters.openai_compat")

DEFAULT_MODEL = "deepseek-v4-flash"


class OpenAICompatProvider(LLMProvider):
    """OpenAI / DeepSeek 等 /chat/completions 兼容端点。"""

    async def chat(self, messages: list[dict], config: dict[str, Any],
                   valid_emotions: set[str] | None = None) -> LLMReply:
        return await asyncio.to_thread(self._request_sync, messages, config,
                                       valid_emotions or set())

    # -- 同步请求(在线程里跑) -------------------------------------------

    def _request_sync(self, messages, config, valid_emotions):
        import requests

        base = str(config.get("base_url", "") or "").strip().rstrip("/")
        key = str(config.get("api_key", "") or "").strip()
        model = str(config.get("model", "") or "").strip() or DEFAULT_MODEL
        if not base or not key:
            return LLMReply("tsundere",
                            "(还没给我配 API 钥匙呢。右键菜单 → 功能 → 设置。)",
                            ok=False, error="missing api config")
        url = base + "/chat/completions"
        try:
            timeout = max(5, int(config.get("timeout", 20)))
        except (TypeError, ValueError):
            timeout = 20
        try:
            max_tokens = max(800, int(config.get("max_tokens", 1500)))
        except (TypeError, ValueError):
            max_tokens = 1500
        try:
            temperature = min(2.0, max(0.0, float(config.get("temperature", 0.8))))
        except (TypeError, ValueError):
            temperature = 0.8

        suffix = build_json_suffix(valid_emotions)
        system = str(messages[0]["content"] if messages and
                     messages[0].get("role") == "system" else "") + suffix
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] +
                        [m for m in messages if m.get("role") != "system"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        effort = str(config.get("reasoning_effort", "") or "").strip().lower()
        if effort in ("low", "medium", "high"):
            payload["reasoning_effort"] = effort
        headers = {"Authorization": "Bearer " + key,
                   "Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except Exception as e:
            _log.warning("api request failed: %s", e)
            return LLMReply("angry", "(信号不太好……待会再聊。)", ok=False, error=str(e))
        if resp.status_code != 200:
            _log.warning("API %s: %s", resp.status_code, resp.text[:200])
            return LLMReply("angry", "(API 出了点问题: HTTP %s)" % resp.status_code,
                            ok=False, error="http %s" % resp.status_code)
        try:
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return LLMReply("sarcastic", "(对面说了些我听不懂的话……)",
                            ok=False, error=str(e))
        if not str(content).strip():
            return LLMReply("sarcastic", "(我想得太入神, 忘了说话……你再说一次?)",
                            ok=False, error="empty content")
        emotion, text = parse_llm_reply(content, valid_emotions)
        return LLMReply(emotion, text, ok=True)


# ----------------------------------------------------------------------
# 纯解析函数(测试/其他适配器可复用)
# ----------------------------------------------------------------------

def parse_llm_reply(content, valid_emotions=None):
    """尽力从模型输出里提取 emotion + text, 任何格式都兜得住。"""
    valid = set(valid_emotions or [])
    text = str(content or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            emotion = str(obj.get("emotion", "default")).strip().lower()
            reply = str(obj.get("text", "")).strip()
            if emotion in valid and reply:
                return emotion, reply
        except Exception:
            pass
    text = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "").strip()
    if not text:
        text = "……"
    return "default", text[:200]


def build_json_suffix(emotion_keys):
    """把当前可用表情注入指令, 约束模型只输出存在的表情。"""
    keys = ", ".join(sorted(emotion_keys)) or "default"
    return (
        "\n无论上述设定如何, 你必须只输出 JSON, 格式: {\"emotion\":\"表情\",\"text\":\"台词\"}。"
        "emotion 只能是: " + keys + " 之一。text 为简短中文台词(一两句话)。"
    )
