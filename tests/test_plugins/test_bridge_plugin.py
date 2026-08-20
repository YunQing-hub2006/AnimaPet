# -*- coding: utf-8 -*-
"""bridge 插件测试(offscreen): 服务装配、窗口绑定、run_on_ui、菜单同步。"""
import json

import pytest
from PyQt6.QtWidgets import QApplication

from anima.core import App
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.loader import LoaderPlugin
from anima.plugins.rule_engine import RuleEnginePlugin
from anima.plugins.state import StatePlugin, StateService
from anima.utils import jsonio, paths
from anima.window.pet_window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def bridge_env(tmp_path, monkeypatch, qapp):
    """共享服务 + 临时 mods(card.ying 最小卡)+ 真内核 App + PetWindow + bridge。"""
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    (mods_dir / "card.ying").mkdir()
    (mods_dir / "card.ying" / "manifest.json").write_text(json.dumps({
        "id": "card.ying", "type": "card", "version": "1.0.0", "name": "影",
        "system_prompt": "人设", "idle_anim": "", "talk_anim": "",
    }, ensure_ascii=False), encoding="utf-8")

    cfg, st = ConfigService(), StateService()
    cfg.load()
    st.load()
    reg = Registry()
    actions = ActionRegistry()
    app = App()
    win = PetWindow(reg, app.bus, cfg, st, actions=actions)
    bridge = BridgePlugin(win)
    plugins = [ConfigPlugin(cfg), StatePlugin(st), ActionsPlugin(actions),
               LoaderPlugin(reg), RuleEnginePlugin(), bridge]
    return app, plugins, win, bridge, mods_dir


async def test_bridge_binds_window_and_actions(bridge_env):
    app, plugins, win, bridge, _ = bridge_env
    await app.start(plugins)
    svc = app.registry.use("bridge")
    assert svc is bridge
    assert win.engine is app.registry.use("rule_engine")   # 引擎已注入
    assert win.char is not None and win.char.id == "card.ying"  # enable 已刷新
    actions = app.registry.use("actions")
    assert actions.get("say") and actions.get("emote") and actions.get("anim")
    assert bridge.window is win
    await app.stop()


async def test_run_on_ui_direct_and_say(bridge_env):
    app, plugins, win, bridge, _ = bridge_env
    await app.start(plugins)
    # 测试环境内核与 Qt 同在主线程 → run_on_ui 直调
    bridge.say("桥上的台词")
    assert win.bubble._full == "桥上的台词"
    bridge.emote("default")   # 无素材也不崩(默认表情回待机)
    assert win.animator.mode == "idle"
    await app.stop()


async def test_menu_registry_sync(bridge_env):
    app, plugins, win, bridge, _ = bridge_env
    await app.start(plugins)
    calls = []
    bridge.add_menu("feature.a", "A 功能", lambda: calls.append("a"))
    bridge.add_menu("feature.b", "B 功能", lambda: calls.append("b"))
    assert [label for label, _ in win.feature_menu] == ["A 功能", "B 功能"]
    # 同 owner 同 label 去重(热重载后重复注册不产生重复项)
    bridge.add_menu("feature.a", "A 功能", lambda: calls.append("a2"))
    assert len(win.feature_menu) == 2
    bridge.remove_menu("feature.a")
    assert [label for label, _ in win.feature_menu] == ["B 功能"]
    win.feature_menu[0][1]()
    assert calls == ["b"]
    await app.stop()


async def test_rule_engine_action_pipeline_through_window(bridge_env):
    """全链路: 事件 → 规则 → 窗口 say 动作 → 气泡台词(含 @idle.this 插值)。"""
    app, plugins, win, bridge, mods_dir = bridge_env
    # 加一个带 @idle.this 规则的行为模组 + 卡内台词
    (mods_dir / "card.ying" / "idle.json").write_text(json.dumps({
        "lines": {"petted": ["别摸啦！"]}}, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "behavior.test").mkdir()
    (mods_dir / "behavior.test" / "manifest.json").write_text(json.dumps({
        "id": "behavior.test", "type": "behavior", "version": "1.0.0", "name": "测试",
        "rules": [{"on": "pet.petted", "then": [{"say": "@idle.this.petted"}]}],
    }, ensure_ascii=False), encoding="utf-8")
    await app.start(plugins)
    app.bus.emit("pet.petted", {"affinity": 1})
    assert win.bubble._full == "别摸啦！"   # 规则经引擎→窗口动作→render_text 全链路
    await app.stop()
