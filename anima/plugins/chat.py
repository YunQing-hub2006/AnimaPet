# -*- coding: utf-8 -*-
"""聊天功能控制器(PLAN Phase 4) —— 由内置功能模组 mods/feature.chat 驱动。

不再作为官方 Plugin 自动启动: 入口/生命周期归 module_manager 管理,
本文件只提供 ChatFeature(FeatureContext 白名单版控制器) + HistoryStore。
"""
from __future__ import annotations

import json
import os
import time

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from anima.adapters import LLMReply, OpenAICompatProvider
from anima.events import EventNames
from anima.utils import jsonio, log, paths
from anima.window.chat_panel import ChatPanel

_log = log.get("chat")

DEFAULT_PROMPT = "你是一只住在屏幕角落的桌面宠物。回复简短(一两句话)。"
MAX_ENTRIES = 300


class HistoryStore:
    """按角色聊天历史存储(单文件, 兼容旧平铺 list)。"""

    format = "anima-chat-1"

    def __init__(self, char_dir: str, char_id: str) -> None:
        self.char_id = str(char_id or "")
        self.path = os.path.join(str(char_dir), "chat_history.json")
        self.conv_id = 1
        self.entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        raw = jsonio.load(self.path, None)
        if isinstance(raw, list):                     # 旧 YingPet 平铺格式
            self.conv_id = 1
            self.entries = self._sanitize(raw)
        elif isinstance(raw, dict):
            try:
                self.conv_id = max(1, int(raw.get("conv_id", 1) or 1))
            except (TypeError, ValueError):
                self.conv_id = 1
            self.entries = self._sanitize(raw.get("messages") or [])
        else:
            self.conv_id = 1
            self.entries = []

    def _sanitize(self, raw) -> list[dict]:
        out = []
        for m in list(raw or [])[-MAX_ENTRIES:]:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", ""))
            content = str(m.get("content", ""))
            if role not in ("user", "assistant") or not content:
                continue
            conv_raw = str(m.get("conv", ""))
            conv = self.conv_id
            if conv_raw.lstrip("-").isdigit():
                conv = max(1, int(conv_raw))
            out.append({
                "role": role, "content": content,
                "ts": str(m.get("ts", "") or ""), "conv": conv,
            })
        return out

    def save(self) -> None:
        jsonio.save(self.path, {
            "format": self.format,
            "character": self.char_id,
            "conv_id": self.conv_id,
            "messages": self.entries,
        })

    def append(self, role: str, content: str) -> dict:
        msg = {
            "role": role, "content": str(content),
            "ts": time.strftime("%m-%d %H:%M"), "conv": self.conv_id,
        }
        self.entries.append(msg)
        self.entries = self.entries[-MAX_ENTRIES:]
        self.save()
        return msg

    def new_conversation(self) -> None:
        self.conv_id += 1
        self.save()

    def clear(self) -> None:
        self.entries = []
        self.conv_id = 1
        self.save()

    def delete_message(self, index: int) -> bool:
        """按全局索引删除单条消息(Phase 4 单条删除)。"""
        if 0 <= int(index) < len(self.entries):
            del self.entries[int(index)]
            self.save()
            return True
        return False

    def delete_conversation(self, conv: int) -> int:
        """删除整个会话, 返回删除条数。"""
        before = len(self.entries)
        self.entries = [m for m in self.entries if int(m.get("conv", 1)) != int(conv)]
        removed = before - len(self.entries)
        if removed:
            self.save()
        return removed

    def search(self, keyword: str) -> list[dict]:
        kw = str(keyword or "")
        return [m for m in self.entries if kw in m.get("content", "")]

    def conversations(self) -> dict[int, list[dict]]:
        groups: dict[int, list[dict]] = {}
        for m in self.entries:
            groups.setdefault(int(m.get("conv", 1)), []).append(m)
        return groups

    def conv_messages(self, conv: int) -> list[dict]:
        return [m for m in self.entries if int(m.get("conv", 1)) == int(conv)]

    def current_conv(self) -> list[dict]:
        return [m for m in self.entries if int(m.get("conv", 1)) == self.conv_id]

    def export_text(self, path: str) -> None:
        lines = ["=== 聊天记录 ==="]
        for m in self.entries:
            ts = m.get("ts", "")
            prefix = "[%s][对话%d] " % (ts, m.get("conv", 1)) if ts else ""
            role = "你" if m.get("role") == "user" else "宠物"
            lines.append("%s%s: %s" % (prefix, role, m.get("content", "")))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def export_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "format": self.format,
                "character": self.char_id,
                "conv_id": self.conv_id,
                "messages": self.entries,
            }, f, ensure_ascii=False, indent=2)

    def import_json(self, path: str) -> int:
        """从外部 JSON 导入(覆盖当前角色历史)。返回导入的消息条数。"""
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        from anima.models import ChatHistory
        if isinstance(raw, list):
            raw = {"format": "yingpet-v4", "character": self.char_id,
                   "conv_id": 1, "messages": raw}
        try:
            model = ChatHistory(**raw)
        except Exception as e:
            raise ValueError("聊天记录 JSON 不合法: %s" % e) from e
        self.conv_id = max(1, model.conv_id)
        self.entries = self._sanitize([m.model_dump() for m in model.messages])
        self.save()
        return len(self.entries)


class ChatFeature:
    """面向 FeatureContext 的聊天控制器(由 mods/feature.chat 启动/停止)。"""

    def __init__(self, ctx, provider=None, panel_factory=None):
        self.ctx = ctx
        self._provider = provider if provider is not None else OpenAICompatProvider()
        self._panel_factory = panel_factory
        self._panel: ChatPanel | None = None
        self._history: HistoryStore | None = None
        self._history_char_id = ""
        self._api_busy = False

    # -- 生命周期(由 feature 模组调用) ----------------------------------

    def start(self) -> None:
        """注册菜单/事件并创建面板(面板经 run_on_ui 到 Qt 线程)。"""
        ctx = self.ctx
        ctx.add_menu_action("聊天窗口 (双击宠物也可以)", self.toggle)
        ctx.on(EventNames.PET_DOUBLE_CLICKED, lambda _p: self.toggle())
        ctx.on(EventNames.MODS_RELOADED, lambda _p: self.refresh_all())
        ctx.on(EventNames.UI_CHANGED, lambda _p: self.apply_skin())
        ctx.on(EventNames.CHARACTER_SWITCHED, lambda _p: self.refresh_all())
        ctx.on(EventNames.STATE_CHANGED, self._on_state_changed)
        ctx.on(EventNames.APP_QUIT, lambda _p: self.stop())
        self.ensure_panel()
        self.refresh_all()

    def stop(self) -> None:
        self.ctx.run_on_ui(self._hide_panel_ui)

    @property
    def panel(self) -> ChatPanel | None:
        return self._panel

    @property
    def history(self) -> HistoryStore | None:
        return self._history

    # -- 面板 --------------------------------------------------------------

    def _make_panel(self) -> None:
        if self._panel is not None:
            return
        panel = self._panel_factory() if self._panel_factory is not None else ChatPanel()
        self._panel = panel
        panel.send_requested.connect(self._send_chat)
        panel.new_conv_requested.connect(self._new_conversation)
        panel.search_requested.connect(self._search_history)
        panel.search_cleared.connect(self._restore_conversation)
        panel.clear_history_requested.connect(self._clear_history)
        panel.export_history_requested.connect(self._export_history)
        panel.export_json_requested.connect(self._export_json)
        panel.import_json_requested.connect(self._import_json)
        panel.card_switch_requested.connect(self._switch_character)
        panel.history_requested.connect(self._show_history)
        panel.history_conv_requested.connect(self._on_history_link)

    def ensure_panel(self) -> None:
        if self._panel is None:
            self.ctx.run_on_ui(self._make_panel)

    def toggle(self) -> None:
        self.ensure_panel()
        panel = self._panel
        if panel is None:
            return
        if panel.isVisible():
            panel.hide()
            return
        pet = self.ctx.pet
        if pet is not None:
            screen = QGuiApplication.screenAt(pet.geometry().center()) or QGuiApplication.primaryScreen()
            x = pet.x() - panel.width() - 12
            if screen and x < screen.availableGeometry().left():
                x = pet.x() + pet.width() + 12
            y = pet.y() + pet.height() - panel.height()
            if screen:
                g = screen.availableGeometry()
                y = max(g.top(), min(y, g.bottom() - panel.height()))
            panel.move(x, y)
        panel.show()
        panel.raise_()
        panel.activateWindow()
        panel.input.setFocus()

    def _hide_panel_ui(self) -> None:
        if self._panel is not None:
            self._panel.hide()

    # -- 刷新/皮肤 ----------------------------------------------------------

    def refresh_all(self) -> None:
        self.ctx.run_on_ui(self._refresh_all_ui)

    def _refresh_all_ui(self) -> None:
        self.ensure_panel()
        panel = self._panel
        if panel is None:
            return
        self.apply_skin_ui()
        cid = self._current_char_id()
        self._history_for(cid)
        panel.set_cards(
            [(c.id, c.name) for c in self.ctx.registry.characters.values()], cid)
        panel.set_affinity(self.ctx.get_state("affinity") or 0)
        self._restore_conversation_ui()

    def apply_skin(self) -> None:
        self.ctx.run_on_ui(self.apply_skin_ui)

    def apply_skin_ui(self) -> None:
        if self._panel is None:
            return
        try:
            skin = self.ctx.registry.ui(self.ctx.config.get("mods", {}).get("ui", ""))
            self._panel.apply_theme(skin.theme if skin else {})
        except Exception as e:
            _log.warning("apply skin: %s", e)

    def _on_state_changed(self, payload) -> None:
        p = payload or {}
        if str(p.get("key", "")) == "affinity":
            val = p.get("value") or 0
            self.ctx.run_on_ui(lambda: self._panel.set_affinity(val)
                               if self._panel is not None else None)

    # -- 角色 --------------------------------------------------------------

    def _current_char_id(self) -> str:
        cid = str(self.ctx.config.get("mods", {}).get("character", "") or "")
        if cid and self.ctx.registry.character(cid) is not None:
            return cid
        chars = self.ctx.registry.characters
        return next(iter(chars)) if chars else ""

    def _current_char(self):
        return self.ctx.registry.character(self._current_char_id())

    def _pet_name(self) -> str:
        c = self._current_char()
        return c.name if c else "影"

    def _history_for(self, cid: str) -> HistoryStore:
        if cid and cid == self._history_char_id and self._history is not None:
            return self._history
        cm = self.ctx.use("character_manager")
        if cid and cm is not None:
            try:
                d = cm.history_dir(cid)
            except ValueError:
                d = os.path.join(paths.DATA_DIR, "chat_history", "default")
        else:
            d = os.path.join(paths.DATA_DIR, "chat_history", "default")
        os.makedirs(d, exist_ok=True)
        self._history_char_id = cid
        self._history = HistoryStore(d, cid)
        return self._history

    def _switch_character(self, char_id: str) -> None:
        cm = self.ctx.use("character_manager")
        if cm is not None:
            cm.switch(str(char_id))

    # -- 收发 --------------------------------------------------------------

    def _send_chat(self, text: str) -> None:
        text = str(text).strip()
        if not text:
            return
        hist = self._history_for(self._current_char_id())
        if self._panel is not None and self._panel.btn_back.isVisible():
            self._restore_conversation_ui()
        hist.append("user", text)
        if self._panel is not None:
            self._panel.add_user(text)
            self._panel.set_status("正在输入…")
        self.ctx.say("……")
        self.ctx.emit(EventNames.CHAT_SEND, {"text": text})
        self.ctx.task(self._ask_api())

    async def _ask_api(self) -> None:
        if self._api_busy:
            return
        self._api_busy = True
        try:
            cid = self._current_char_id()
            char = self._current_char()
            prompt = char.system_prompt if char else DEFAULT_PROMPT
            emote_keys = list(self.ctx.registry.character_emotes(cid).keys())
            msgs = self._history_for(cid).current_conv()[-10:]
            config = self.ctx.config.get("api", {}) or {}
            reply = await self._provider.chat(
                msgs, config, valid_emotions=set(emote_keys))
            self.ctx.run_on_ui(self._on_api_done_ui, reply)
        except Exception as e:
            _log.warning("ask api: %s", e)
            failure = LLMReply("sarcastic", "(信号不太好……待会再聊。)", ok=False, error=str(e))
            self.ctx.run_on_ui(self._on_api_done_ui, failure)
        finally:
            self._api_busy = False

    def _on_api_done_ui(self, reply: LLMReply) -> None:
        panel = self._panel
        if panel is None:
            return
        panel.set_status("")
        if panel.btn_back.isVisible():
            self._restore_conversation_ui()
        if not reply.ok:
            panel.add_system("回复失败: " + str(reply.text))
            return
        self._history_for(self._current_char_id()).append("assistant", reply.text)
        panel.add_pet(reply.text, self._pet_name())
        cur = int(self.ctx.get_state("affinity") or 0) + 2
        self.ctx.set_state("affinity", cur)
        self.ctx.say(reply.text)
        self.ctx.emit(EventNames.CHAT_REPLY, {
            "ok": True, "emotion": str(reply.emotion), "text": str(reply.text),
        })

    # -- 历史/会话 ----------------------------------------------------------

    def _new_conversation(self) -> None:
        self._history_for(self._current_char_id()).new_conversation()
        if self._panel is not None:
            self._panel.btn_back.hide()
            self._panel.clear()
            self._panel.add_system("—— 新对话开始了 ——")

    def _clear_history(self) -> None:
        panel = self._panel
        if panel is None:
            return
        r = QMessageBox.question(
            panel, "清空历史", "确定要清空全部聊天记录吗? 清空后不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        self._history_for(self._current_char_id()).clear()
        panel.btn_back.hide()
        panel.clear()
        panel.add_system("—— 历史记录已清空 ——")

    def _export_history(self) -> None:
        panel = self._panel
        if panel is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            panel, "导出聊天记录", "聊天记录.txt",
            "文本文件 (*.txt);;所有文件 (*.*)")
        if not path:
            return
        try:
            self._history_for(self._current_char_id()).export_text(path)
            panel.add_system("已导出到: " + os.path.basename(path))
        except Exception as e:
            _log.warning("export history: %s", e)
            panel.add_system("导出失败: " + str(e))

    def _export_json(self) -> None:
        panel = self._panel
        if panel is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            panel, "导出聊天 JSON", "聊天记录.json",
            "JSON (*.json);;所有文件 (*.*)")
        if not path:
            return
        try:
            self._history_for(self._current_char_id()).export_json(path)
            panel.add_system("已导出 JSON: " + os.path.basename(path))
        except Exception as e:
            _log.warning("export json: %s", e)
            panel.add_system("导出失败: " + str(e))

    def _import_json(self) -> None:
        panel = self._panel
        if panel is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            panel, "导入聊天 JSON", "", "JSON (*.json);;所有文件 (*.*)")
        if not path:
            return
        try:
            n = self._history_for(self._current_char_id()).import_json(path)
            panel.add_system("已导入 %d 条聊天记录。" % n)
            self._restore_conversation_ui()
        except Exception as e:
            _log.warning("import json: %s", e)
            panel.add_system("导入失败: " + str(e))

    def _restore_conversation(self) -> None:
        self._restore_conversation_ui()

    def _restore_conversation_ui(self) -> None:
        panel = self._panel
        if panel is None or self._history is None:
            return
        panel.clear()
        name = self._pet_name()
        for m in self._history.current_conv():
            if m["role"] == "user":
                panel.add_user(m["content"])
            else:
                panel.add_pet(m["content"], name)
        panel.btn_back.hide()

    def _search_history(self, kw: str) -> None:
        panel = self._panel
        if panel is None:
            return
        panel.clear()
        hits = self._history_for(self._current_char_id()).search(kw)
        panel.add_system("搜索「%s」: 共 %d 条" % (kw, len(hits)))
        for m in hits:
            prefix = "[%s] " % m.get("ts", "") if m.get("ts") else ""
            if m["role"] == "user":
                panel.add_user(prefix + m["content"])
            else:
                panel.add_pet(prefix + m["content"])

    def _show_history(self) -> None:
        panel = self._panel
        if panel is None:
            return
        panel.btn_back.show()
        panel.clear()
        groups = self._history_for(self._current_char_id()).conversations()
        if not groups:
            panel.add_system("还没有历史对话。先聊几句吧。")
            return
        t = panel._theme
        panel.add_system("—— 历史对话列表（点链接查看；点“返回”回到当前对话）——")
        for conv in sorted(groups, reverse=True):
            msgs = groups[conv]
            ts = str(msgs[0].get("ts", "") or "")
            first = next((str(m.get("content", "")) for m in msgs if m.get("role") == "user"),
                         str(msgs[0].get("content", "")))
            snippet = ChatPanel.esc(first)
            if len(snippet) > 30:
                snippet = snippet[:30] + "…"
            cur = "（当前）" if conv == self._history.conv_id else ""
            panel.browser.append(
                '<div style="margin:5px 0;">'
                '<a href="conv:%d" style="color:%s; font-weight:bold; text-decoration:none;">'
                '[对话 %d]</a>'
                ' <span style="color:%s;">%s ｜ %d 条 %s</span><br>'
                '<span style="color:%s; font-size:11px;">%s</span></div>'
                % (conv, t["accent"], conv, t["status_fg"], ts, len(msgs), cur,
                   t["fg_browser"], snippet))

    def _on_history_link(self, url) -> None:
        text = str(url)
        if not text.startswith("conv:"):
            return
        try:
            self._view_history_conv(int(text[5:]))
        except ValueError:
            pass

    def _view_history_conv(self, conv: int) -> None:
        panel = self._panel
        if panel is None:
            return
        panel.clear()
        name = self._pet_name()
        msgs = self._history_for(self._current_char_id()).conv_messages(conv)
        panel.add_system(
            "—— 正在浏览 对话 %d（%d 条）｜ 点“返回”回到当前对话 ——" % (conv, len(msgs)))
        for m in msgs:
            prefix = "[%s] " % m.get("ts", "") if m.get("ts") else ""
            if m["role"] == "user":
                panel.add_user(prefix + m["content"])
            else:
                panel.add_pet(prefix + m["content"], name)
        panel.btn_back.show()