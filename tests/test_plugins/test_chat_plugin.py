# -*- coding: utf-8 -*-
"""Phase 4 聊天插件测试: 解析/历史/面板/按角色隔离/浏览/LLM 降级。

AnimaPet 等价体(自 YingPet-v4 tests/test_chat_plugin.py 改写)。
"""
import asyncio
import json
import os

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from anima.adapters import LLMProvider, LLMReply
from anima.adapters.openai_compat import build_json_suffix, parse_llm_reply
from anima.core import App
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.character_manager import CharacterManagerPlugin
from anima.plugins.chat import ChatPlugin, HistoryStore
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.loader import LoaderPlugin
from anima.plugins.module_manager import ModuleManagerPlugin
from anima.plugins.rule_engine import RuleEnginePlugin
from anima.plugins.state import StatePlugin, StateService
from anima.utils import jsonio, paths
from anima.window.pet_window import PetWindow


class FakeProvider(LLMProvider):
    """返回固定回复的假适配器(不发网络请求)。"""

    def __init__(self, notes=None):
        self.notes = list(notes or ["你好呀。"])
        self.calls = []

    async def chat(self, messages, config, valid_emotions=None):
        self.calls.append(dict(messages=list(messages), config=config))
        text = self.notes.pop(0) if self.notes else "……"
        return LLMReply("tsundere", text, ok=True)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def chat_env(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    for mid in ("card.ying", "card.two"):
        (mods_dir / mid).mkdir()
        (mods_dir / mid / "manifest.json").write_text(json.dumps({
            "id": mid, "type": "card", "version": "1.0.0",
            "name": mid, "system_prompt": "人设 " + mid,
            "idle_anim": "", "talk_anim": "",
        }, ensure_ascii=False), encoding="utf-8")
        (mods_dir / mid / "emotes.json").write_text(json.dumps({
            "emotes": {"default": {"name": "平时", "lines": ["……"]},
                         "angry": {"name": "生气", "lines": ["哼"]}},
        }, ensure_ascii=False), encoding="utf-8")
        (mods_dir / mid / "idle.json").write_text(json.dumps({
            "interval_min": 30, "interval_max": 42,
            "lines": {"default": ["空闲"]},
        }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    cfg, st = ConfigService(), StateService()
    cfg.load()
    st.load()
    cfg.set("mods.character", "card.ying")
    cfg.save()
    reg = Registry()
    actions = ActionRegistry()
    app = App()
    win = PetWindow(reg, app.bus, cfg, st, actions=actions)
    bridge = BridgePlugin(win)
    chat_plugin = ChatPlugin(provider=FakeProvider())
    plugins = [ConfigPlugin(cfg), StatePlugin(st), ActionsPlugin(actions),
               LoaderPlugin(reg), RuleEnginePlugin(), CharacterManagerPlugin(),
               bridge, ModuleManagerPlugin(), chat_plugin]
    return app, plugins, win, chat_plugin, mods_dir


async def start(env):
    app, plugins, *_ = env
    await app.start(plugins)
    return app


# ---------------------------------------------------------------------
# 解析/历史纯函数
# ---------------------------------------------------------------------

def test_parse_llm_reply_and_suffix():
    emo, text = parse_llm_reply('{"emotion":"tsundere","text":"哼。"}',
                                {"default", "tsundere"})
    assert (emo, text) == ("tsundere", "哼。")
    emo, text = parse_llm_reply("随便一句回复", {"default"})
    assert emo == "default" and text == "随便一句回复"
    suffix = build_json_suffix({"default", "angry"})
    assert "angry" in suffix and "JSON" in suffix


def test_history_store_crud_export_import(tmp_path, monkeypatch):
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    d = tmp_path / "data" / "characters" / "card.ying"
    d.mkdir(parents=True)
    store = HistoryStore(str(d), "card.ying")
    store.append("user", "第一条")
    store.append("assistant", "第一条回复")
    store.new_conversation()
    store.append("user", "第二条")
    assert store.conv_id == 2
    assert [m["content"] for m in store.current_conv()] == ["第二条"]
    assert [m["content"] for m in store.conv_messages(1)] == ["第一条", "第一条回复"]
    assert store.search("第一条")
    assert json.loads((d / "chat_history.json").read_text(encoding="utf-8"))["format"] == "anima-chat-1"
    assert store.delete_message(0) is True
    assert store.delete_conversation(1) == 1
    assert [m["content"] for m in store.entries] == ["第二条"]

    out = tmp_path / "history.json"
    store.export_json(str(out))
    other = HistoryStore(str(d), "card.ying")
    other.import_json(str(out))
    assert other.conv_id == store.conv_id
    assert len(other.entries) == len(store.entries)


# ---------------------------------------------------------------------
# 插件集成
# ---------------------------------------------------------------------

async def test_chat_plugin_menu_toggle_close_hides(chat_env):
    app, _, win, chat, _ = chat_env
    await start(chat_env)
    assert chat.panel is not None
    assert any("聊天窗口" in label for label, _ in win.feature_menu)
    chat._toggle()
    assert chat.panel.isVisible()
    chat.panel.close()
    assert not chat.panel.isVisible(), "聊天窗关闭应只隐藏"
    await app.stop()


async def test_chat_send_stores_history_per_character(chat_env):
    app, _, win, chat, mods_dir = chat_env
    await start(chat_env)
    cm = app.registry.use("character_manager")
    chat._send_chat("你好")
    await asyncio.sleep(0.15)
    assert len(chat.history.entries) == 2          # user + assistant
    assert chat.history.entries[1]["content"] == "你好呀。"

    ying_file = os.path.join(paths.DATA_DIR, "characters", "card.ying", "chat_history.json")
    assert os.path.exists(ying_file)

    # 切到 card.two: 历史按角色分目录
    assert cm.switch("card.two") is True
    await asyncio.sleep(0)
    chat._send_chat("那边你好")
    await asyncio.sleep(0.15)
    assert chat._history_char_id == "card.two"
    two_file = os.path.join(paths.DATA_DIR, "characters", "card.two", "chat_history.json")
    assert os.path.exists(two_file)
    with open(two_file, encoding="utf-8") as f:
        two_raw = json.load(f)
    assert any(m["content"] == "那边你好" for m in two_raw["messages"])
    with open(ying_file, encoding="utf-8") as f:
        ying_raw = json.load(f)
    assert any(m["content"] == "你好" for m in ying_raw["messages"])
    await app.stop()


async def test_chat_history_browse_and_back(chat_env):
    app, _, _, chat, _ = chat_env
    await start(chat_env)
    chat._send_chat("第一条消息")
    await asyncio.sleep(0.15)
    chat._new_conversation()
    chat._send_chat("第二条消息")
    await asyncio.sleep(0.15)
    chat._show_history()
    text = chat.panel.browser.toPlainText()
    assert "[对话 1]" in text and "[对话 2]" in text
    chat._on_history_link("conv:1")
    view = chat.panel.browser.toPlainText()
    assert "第一条消息" in view and "第二条消息" not in view
    chat.panel._do_back()
    cur = chat.panel.browser.toPlainText()
    assert "第二条消息" in cur
    await app.stop()


def test_openai_provider_missing_config_degrades():
    import asyncio
    from anima.adapters import OpenAICompatProvider

    async def run():
        reply = await OpenAICompatProvider().chat(
            [{"role": "user", "content": "hi"}], {})
        return reply

    reply = asyncio.run(run())
    assert reply.ok is False
    assert "API" in reply.text