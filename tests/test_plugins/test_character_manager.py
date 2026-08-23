# -*- coding: utf-8 -*-
"""character_manager 插件测试: 当前角色解析 + 程序化切换 + character.switch/switched 事件链。"""
import json
import os

import pytest
from PyQt6.QtWidgets import QApplication

from anima.core import App
from anima.events import EventNames
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.character_manager import CharacterManagerPlugin
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
def stack(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    for mid in ("card.ying", "card.two"):
        (mods_dir / mid).mkdir()
        (mods_dir / mid / "manifest.json").write_text(json.dumps({
            "id": mid, "type": "card", "version": "1.0.0", "name": mid,
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
               LoaderPlugin(reg), RuleEnginePlugin(), bridge,
               CharacterManagerPlugin()]
    return app, plugins, win


async def start(stack):
    app, plugins, _win = stack
    await app.start(plugins)
    return app


async def test_current_resolution(stack):
    app = await start(stack)
    cm = app.registry.use("character_manager")
    # config 未指定 → 第一个启用的(扫描按目录名排序, card.two < card.ying)
    assert cm.active_id() == "card.two"
    assert cm.current() is not None and cm.current().id == "card.two"
    assert [c.id for c in cm.characters().values()] == ["card.two", "card.ying"]
    await app.stop()


async def test_switch_chain(stack):
    """switch → character.switch → 窗口刷新 → character.switched + 台词 + 引擎同步。"""
    app, plugins, win = stack
    await app.start(plugins)
    cm = app.registry.use("character_manager")
    switched = []
    app.bus.subscribe(EventNames.CHARACTER_SWITCHED, lambda d: switched.append(d))

    assert cm.switch("card.ying") is True
    assert cm.active_id() == "card.ying"
    assert cm.config.get("mods.character") == "card.ying"
    assert win.char is not None and win.char.id == "card.ying"      # 窗口已刷新
    assert win.bubble._full == "已切换角色卡: card.ying"
    assert any(d and d.get("character") == "card.ying" for d in switched)
    reg = app.registry.use("mods")
    assert reg.active_char_id == "card.ying"                        # @idle.this 解析源
    engine = app.registry.use("rule_engine")
    assert engine._char_id == "card.ying"                           # 行为归属隔离
    await app.stop()


async def test_switch_rejects_unknown(stack):
    app = await start(stack)
    cm = app.registry.use("character_manager")
    assert cm.switch("card.nope") is False
    assert cm.config.get("mods.character", "") == ""               # 配置未被写坏
    await app.stop()


async def test_current_falls_back_when_config_stale(stack):
    """config 指向不存在/未启用的角色 → current() 回落第一个启用的。"""
    app = await start(stack)
    cm = app.registry.use("character_manager")
    cm.config.set("mods.character", "card.nope")
    assert cm.active_id() == "card.two"
    assert cm.current().id == "card.two"
    await app.stop()


# ----------------------------------------------------------------------
# Phase 3: card_model / history_dir
# ----------------------------------------------------------------------

async def test_card_model_returns_aggregate(stack):
    app = await start(stack)
    cm = app.registry.use("character_manager")
    card = cm.card_model("card.ying")
    assert card.id == "card.ying"
    assert card.behaviors == []          # fixture 卡没有子文件 → 聚合为空列表
    await app.stop()


async def test_card_model_bad_card_raises(stack):
    app = await start(stack)
    cm = app.registry.use("character_manager")
    mf = os.path.join(paths.MODS_DIR, "card.ying", "manifest.json")
    with open(mf, "r", encoding="utf-8") as f:
        orig = f.read()
    try:
        with open(mf, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "", "type": "card"}))
        with pytest.raises(ValueError, match="id"):
            cm.card_model("card.ying")
    finally:
        with open(mf, "w", encoding="utf-8") as f:
            f.write(orig)
    await app.stop()


async def test_history_dir_creates_and_validates(stack, tmp_path, monkeypatch):
    app = await start(stack)
    cm = app.registry.use("character_manager")
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path / "data"))
    d = cm.history_dir("card.ying")
    assert d == str(tmp_path / "data" / "characters" / "card.ying")
    assert os.path.isdir(d)
    with pytest.raises(ValueError):
        cm.history_dir("../evil")
    await app.stop()
