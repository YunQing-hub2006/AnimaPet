# -*- coding: utf-8 -*-
"""ui.* 皮肤模组测试(改写自 YingPet tests/test_ui_mod.py, 聊天面板部分属 Phase 4 已剔除)。

覆盖: 皮肤注册 / 窗口气泡与菜单应用 / 切换写回 / 热增删 / 坏主题兜底 / 开关。
"""
import json
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from anima.core import App
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.loader import LoaderPlugin
from anima.plugins.module_manager import ModuleManagerPlugin
from anima.plugins.rule_engine import RuleEnginePlugin
from anima.plugins.state import StatePlugin, StateService
from anima.utils import jsonio, paths, theme
from anima.window.pet_window import PetWindow

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def env(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    for name in ("ui.default", "ui.dark", "ui.sakura"):
        shutil.copytree(REPO_ROOT / "mods" / name, mods_dir / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
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
               LoaderPlugin(reg), RuleEnginePlugin(), bridge, ModuleManagerPlugin()]
    return app, plugins, win, mods_dir


async def start(env):
    app, plugins, _win, _mods = env
    await app.start(plugins)
    return app


async def test_ui_mods_registered(env):
    app = await start(env)
    reg = app.registry.use("mods")
    assert {"ui.default", "ui.dark", "ui.sakura"} <= set(reg.uis)
    assert reg.ui("ui.dark").theme["accent"] == "#4a9eff"
    await app.stop()


async def test_skin_applies_to_bubble_and_menu(env):
    app, _plugins, win, _mods = env
    await app.start(_plugins)
    cfg = app.registry.use("config")
    cfg.set("mods.ui", "ui.sakura")
    win.refresh_from_registry()
    assert "#e07a9e" in win.bubble.label.styleSheet()
    assert "#e07a9e" in win._menu_qss()
    win._switch_ui("ui.dark")
    assert cfg.get("mods.ui") == "ui.dark"
    assert "#4a9eff" in win._menu_qss()
    await app.stop()


async def test_hot_add_remove_ui_mod(env):
    app, _plugins, win, mods_dir = env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    hot = mods_dir / "ui.test_hot"
    hot.mkdir()
    (hot / "manifest.json").write_text(json.dumps({
        "id": "ui.test_hot", "type": "ui", "name": "热皮肤",
        "theme": {"accent": "#0000ff", "bubble_bg": "#111111",
                  "menu_bg": "#222222", "menu_hover": "#333333"}}), encoding="utf-8")
    mm.rescan()
    assert "ui.test_hot" in mm.registry.uis
    mm.config.set("mods.ui", "ui.test_hot")
    win._apply_skin()
    assert "#111111" in win.bubble.label.styleSheet()
    assert "#222222" in win._menu_qss() and "#333333" in win._menu_qss()
    shutil.rmtree(hot)
    mm.rescan()
    assert "ui.test_hot" not in mm.registry.uis
    win._apply_skin()   # 皮肤没了 → 回退默认, 不崩
    assert "#111111" not in win.bubble.label.styleSheet()
    await app.stop()


async def test_bad_theme_fallback(env):
    app, _plugins, win, mods_dir = env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    bad = mods_dir / "ui.test_bad"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({
        "id": "ui.test_bad", "type": "ui", "name": "坏皮肤",
        "theme": {"accent": 123, "font_size": None}}), encoding="utf-8")
    mm.rescan()
    assert "ui.test_bad" in mm.registry.uis
    mm.config.set("mods.ui", "ui.test_bad")
    win._apply_skin()
    assert theme.DEFAULT_THEME["bubble_bg"] in win.bubble.label.styleSheet()
    await app.stop()


async def test_ui_mod_toggle(env):
    app, _plugins, _win, _mods = env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    await mm.set_enabled("ui.dark", False)
    assert "ui.dark" not in mm.registry.uis
    await mm.set_enabled("ui.dark", True)
    assert "ui.dark" in mm.registry.uis
    await app.stop()
