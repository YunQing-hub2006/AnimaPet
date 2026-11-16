# -*- coding: utf-8 -*-
"""window 三件套测试(offscreen): 构造注入、动作注册、交互事件、表现 API。"""
import json
import threading
import time

import pytest
from PyQt6.QtWidgets import QApplication, QLabel

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


class _CountingLabel(QLabel):
    """记录每一次 setPixmap(用于验证"同一帧不重复画")。"""

    def __init__(self):
        super().__init__()
        self.painted = []

    def setPixmap(self, pm):
        self.painted.append(pm)
        super().setPixmap(pm)


def test_animator_skips_redundant_repaint(qapp):
    """同一张帧不重复 setPixmap。

    静态表情(单图无动画)与单帧动画每 80~90ms 拿到的都是同一个 QPixmap 对象;
    修复前实测 100 次 tick 里有 99 次内容完全没变, 却照样触发 update()
    让整个半透明窗口重新合成。
    """
    from PyQt6.QtGui import QPixmap

    lab = _CountingLabel()
    anim = Animator(lab, None, _FakeBus(), 180)
    anim.anim_timer.stop()
    single = QPixmap(4, 4)
    anim.play_frames = [single]
    anim.mode = "anim"
    for _ in range(10):
        anim.advance()
    assert len(lab.painted) == 1               # 单帧动画只画一次
    assert anim._last_pm is single

    # 交替帧每次内容都不同 -> 每次都真的重画
    lab2 = _CountingLabel()
    anim2 = Animator(lab2, None, _FakeBus(), 180)
    anim2.anim_timer.stop()
    anim2.play_frames = [QPixmap(4, 4), QPixmap(4, 4)]
    anim2.mode = "anim"
    for _ in range(10):
        anim2.advance()
    assert len(lab2.painted) == 10


def test_prefetch_fills_frame_group(qapp, tmp_path):
    """整组帧由后台解码补齐: 主线程只同步解第一帧。

    冷启动/换角色卡时整组同步解码实测 ~96ms(tools/bench_anim.py),
    所以 instant_frames 只给首帧, 其余交给 prefetch, 解完经 queued signal
    回到主线程写进缓存。
    """
    from PyQt6.QtGui import QPixmap

    from anima.mods import loader as L

    frames_dir = tmp_path / "anims" / "idle" / "frames"
    frames_dir.mkdir(parents=True)
    for i in range(5):
        pm = QPixmap(8, 8)
        pm.fill()
        assert pm.save(str(frames_dir / ("frame_%04d.png" % i)))

    anim = L.AnimMod(id="t:idle", dir=str(tmp_path / "anims" / "idle"))
    size = 16
    L.clear_frame_cache()

    # 未缓存: 只给首帧, 且绝不把"只有一帧"的结果写进缓存
    assert len(L.instant_frames(anim, size)) == 1
    assert not L.is_cached(anim, size)
    # 同步兜底路径仍然完整(reg.anim(...).frames() 的既有语义不能变)
    assert len(anim.frames(size)) == 5

    # 后台路径: 解完整组并回主线程安装
    L.clear_frame_cache()
    done = threading.Event()
    L.prefetch([anim], size, done.set)
    deadline = time.time() + 5.0
    while not done.is_set() and time.time() < deadline:
        qapp.processEvents()          # queued signal 靠事件循环投递
        time.sleep(0.01)
    assert done.is_set(), "后台预解码未在 5s 内回调"
    assert L.is_cached(anim, size)
    assert len(L.instant_frames(anim, size)) == 5


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


def test_dialog_style_follows_current_skin(qapp):
    """对话框样式跟随当前皮肤, 不再写死默认主题。

    早先 apply_dialog_style 里是 merge_theme({}), 于是换了浅色皮肤后主窗口 /
    气泡 / 聊天面板都变浅了, 四个对话框还是深紫。
    """
    from PyQt6.QtWidgets import QDialog

    from anima.utils import theme
    from anima.window.dialogs.common import apply_dialog_style

    light = {"bg_window": "#fff5f8", "fg_panel": "#5a3a48", "accent": "#e07a9e"}

    class _Skin:
        def __init__(self, t):
            self.theme = t

    class _Host:
        def __init__(self, skin):
            self.registry = type(
                "R", (), {"ui": staticmethod(lambda mid: skin)})()
            self.config = type("C", (), {"get": staticmethod(lambda k, d=None: "ui.x")})()

    dlg = QDialog()
    dlg.mm = _Host(_Skin(light))
    apply_dialog_style(dlg)
    qss = dlg.styleSheet()

    merged = theme.merge_theme(light)
    assert merged["bg_window"] in qss          # 用上了皮肤的底色
    assert theme.DEFAULT_THEME["fg_panel"] not in qss   # 没残留默认前景色

    # 拿不到 host 时回落默认主题, 行为跟以前一致
    plain = QDialog()
    apply_dialog_style(plain)
    assert plain.styleSheet() == theme.dialog_qss(theme.merge_theme({}))
