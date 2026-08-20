# -*- coding: utf-8 -*-
"""window 三件套测试(offscreen): 构造注入、动作注册、交互事件、表现 API。"""
import json

import pytest
from PyQt6.QtWidgets import QApplication

from anima.events import EventNames
from anima.mods.loader import BehaviorMod, CharacterMod, IdlePack
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry
from anima.plugins.config import ConfigService
from anima.plugins.state import StateService
from anima.utils import jsonio, paths
from anima.window.animator import Animator
from anima.window.bubble import Bubble
from anima.window.pet_window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def env(tmp_path, monkeypatch):
    """共享服务 + 临时 data 路径; registry 内存构造(卡/表情/台词/行为)。"""
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    cfg = ConfigService()
    cfg.load()
    st = StateService()
    st.load()
    reg = Registry()
    reg.apply([
        CharacterMod(id="card.ying", dir="", name="影", system_prompt="人设",
                     idle_anim="", talk_anim=""),
        IdlePack(id="card.ying:idle", dir="", name="影台词", character="card.ying",
                 sections={"default": ["你好"], "petted": ["别摸啦"]}),
        BehaviorMod(id="behavior.x", dir="", name="x",
                    rules=[{"on": "pet.petted", "then": [{"say": "@idle.this.petted"}]}]),
    ])
    reg.active_char_id = ""
    return cfg, st, reg


def make_window(env, qapp, actions=None, engine=None, bus=None):
    cfg, st, reg = env
    bus = bus if bus is not None else _FakeBus()
    win = PetWindow(reg, bus, cfg, st, actions=actions, engine=engine)
    return win, bus


class _FakeBus:
    """只有 emit 的迷你总线(窗口测试不跑内核)。"""

    def __init__(self):
        self.events = []
        self._subs = {}

    def emit(self, name, payload=None):
        self.events.append((name, payload))
        for h in self._subs.get(name, []):
            h(payload)

    def subscribe(self, name, handler):
        self._subs.setdefault(name, []).append(handler)


def test_window_constructs_and_refreshes(env, qapp):
    actions = ActionRegistry()
    engine_calls = []

    class Engine:
        def set_character(self, cid):
            engine_calls.append(cid)

    win, _ = make_window(env, qapp, actions=actions, engine=Engine())
    cfg, _, reg = env
    assert win.display_size == 180                       # DEFAULT_CONFIG window.size=small
    assert win.char is not None and win.char.id == "card.ying"
    assert reg.active_char_id == "card.ying"
    assert engine_calls == ["card.ying"]                 # refresh 同步引擎
    assert actions.get("say") is not None                # 构造时注册表现动作
    assert actions.get("emote") is not None
    assert actions.get("anim") is not None
    win.close()


def test_petted_updates_state_and_emits(env, qapp):
    win, bus = make_window(env, qapp)
    cfg, st, _ = env
    win._on_petted()
    assert st.get("affinity") == 1
    assert (EventNames.PET_PETTED, {"affinity": 1}) in bus.events
    win.close()


def test_say_action_interpolates(env, qapp):
    actions = ActionRegistry()
    win, _ = make_window(env, qapp, actions=actions)
    say = actions.get("say")
    say("@idle.this.petted", {"state": {}, "event": {}, "config": {}}, {"say": "@idle.this.petted"})
    assert win.bubble._full == "别摸啦"
    assert win.bubble.is_typing()
    win.close()


def test_switch_character_writes_config_service(env, qapp):
    win, bus = make_window(env, qapp)
    cfg, _, reg = env
    reg.apply([CharacterMod(id="card.two", dir="", name="二", system_prompt="",
                            idle_anim="", talk_anim="")])
    win._switch_character("card.two")
    assert cfg.get("mods.character") == "card.two"
    assert win.char.id == "card.two"
    assert any(name == EventNames.CHARACTER_SWITCHED and p["character"] == "card.two"
               for name, p in bus.events)
    assert win.bubble._full == "已切换角色卡: 二"
    win.close()


def test_switch_ui_and_size(env, qapp):
    from anima.mods.loader import UiMod
    win, bus = make_window(env, qapp)
    cfg, _, reg = env
    reg.apply([UiMod(id="ui.dark", dir="", name="暗色", theme={})])
    win._switch_ui("ui.dark")
    assert cfg.get("mods.ui") == "ui.dark"
    assert any(name == EventNames.UI_CHANGED for name, _ in bus.events)
    win._set_size("large")
    assert cfg.get("window.size") == "large"
    assert win.display_size == 320
    win._toggle_sit()
    assert cfg.get("window.sit_reminder") is False
    win._toggle_sit()
    assert cfg.get("window.sit_reminder") is True
    win.close()


def test_animator_state_machine(env, qapp):
    win, _ = make_window(env, qapp)
    anim = win.animator
    anim.set_frames([], [])
    anim.back_to_idle()
    assert anim.mode == "idle"
    assert anim.frame_idx == 0
    # 未知表情安全回退
    anim.set_emotion("no_such_emote")
    assert anim.mode == "idle"
    # 未知动画忽略
    anim.play_anim("no_such_anim")
    assert anim.mode == "idle"
    win.close()


def test_bubble_typing_and_theme(env, qapp):
    win, _ = make_window(env, qapp)
    b = win.bubble
    b.say("你好世界", hold_ms=100)
    assert b.is_typing()
    for _ in range(20):
        b._tick()
    assert b._full == "你好世界"
    b.apply_theme({"bubble_bg": "#000000"})   # 皮肤键合并, 不崩
    b.close()
    win.close()
