# -*- coding: utf-8 -*-
"""hotreload 插件测试: watcher 防抖/路径刷新/经内核线程重扫 + bridge 窗口刷新订阅。"""
import json
import time

import pytest
from PyQt6.QtWidgets import QApplication

from anima.core import App
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.hotreload import HotreloadPlugin, ModsWatcher
from anima.plugins.loader import LoaderPlugin
from anima.plugins.module_manager import ModuleManagerPlugin
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
               LoaderPlugin(reg), RuleEnginePlugin(), bridge,
               ModuleManagerPlugin(), HotreloadPlugin()]
    return app, plugins, win, mods_dir


def test_watcher_debounce_coalesces(qapp, tmp_path):
    """连发目录变更 → 只触发一次重扫(防抖)。"""
    calls = []
    w = ModsWatcher(str(tmp_path), debounce_ms=80, rescan=lambda: calls.append(1))
    w.start()
    w._on_dir_changed("")
    w._on_dir_changed("")
    w._on_dir_changed("")
    assert not calls                       # 防抖窗口内不触发
    deadline = time.time() + 2
    while not calls and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert calls == [1]                    # 只重扫一次
    w.stop()


def test_watcher_watches_mods_dir_and_subdirs(qapp, tmp_path):
    sub = tmp_path / "mods" / "card.x"
    sub.mkdir(parents=True)
    w = ModsWatcher(str(tmp_path / "mods"), debounce_ms=80)
    w.start()
    dirs = w._fs.directories()
    assert str(tmp_path / "mods") in dirs
    assert str(sub) in dirs
    w.stop()
    assert not w._fs.directories()


async def test_hotreload_plugin_wires_rescan(stack):
    """插件 enable 后: watcher 起在 Qt 线程, _do_reload 触发真实重扫(新模组生效)。"""
    app, plugins, win, mods_dir = stack
    await app.start(plugins)
    mm = app.registry.use("module_manager")
    hp = next(p for p in plugins if p.name == "hotreload")
    assert hp.watcher is not None            # enable 时已在 Qt 线程创建

    (mods_dir / "ui.dark").mkdir()
    (mods_dir / "ui.dark" / "manifest.json").write_text(json.dumps({
        "id": "ui.dark", "type": "ui", "name": "暗色", "theme": {}}), encoding="utf-8")

    # 内核线程(测试主线程)直调 _do_reload → rescan 同步路径
    hp.watcher._do_reload()
    assert mm.registry.uis.get("ui.dark") is not None
    await app.stop()


async def test_bridge_refreshes_window_on_reload(stack):
    """mods.reloaded → bridge 把窗口刷新封送到 Qt 线程。"""
    app, plugins, win, mods_dir = stack
    await app.start(plugins)
    refreshed = []
    win.refresh_from_registry = lambda: refreshed.append(1)

    loader = next(p for p in plugins if p.name == "loader")
    loader.rescan()
    assert refreshed == [1]                  # 主线程直调(测试环境)
    await app.stop()
