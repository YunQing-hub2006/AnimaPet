# -*- coding: utf-8 -*-
"""五个功能模组测试(改写自 YingPet tests/test_plugins_v31.py)。

不发真实网络请求(weather 只测纯解析 + B2 禁用丢弃迟到回调); 插件代码直接从
仓库 mods/feature.* 复制进 tmp 模组目录, 测的就是真实交付物。
1. 全量自动启用 + 菜单登记
2. clock: 台词函数 + 菜单开关持久化
3. weather: parse_wttr/parse_open_meteo/weather_text + 禁用时断开 done/丢弃迟到回调
4. todo: 窗口增删勾选 + state.json 持久化 + 每日播报(当天不重复)
5. sysmon: sample_system 真实采样(Windows) + 台词函数
6. packer: 窗口列表渲染 + 类型判定(纯函数闭环已在 module_manager 测试覆盖)
"""
import asyncio
import importlib
import json
import shutil
import sys
import time
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
from anima.utils import jsonio, paths
from anima.window.pet_window import PetWindow

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES = ("feature.clock", "feature.weather", "feature.todo",
            "feature.sysmon", "feature.packer")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def feats_env(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    # 真实交付物: 从仓库复制五个功能模组
    for name in FEATURES:
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
    return app, plugins, win


async def start(feats_env):
    app, plugins, _win = feats_env
    await app.start(plugins)
    return app


def _ns(mid):
    mod_name = "mods_" + mid.replace(".", "_")
    assert mod_name in sys.modules, mod_name
    return vars(importlib.import_module(mod_name))


async def test_all_features_auto_enabled(feats_env):
    app, _plugins, win = feats_env
    await app.start(_plugins)
    reg = app.registry.use("mods")
    labels = [lbl for lbl, _ in win.feature_menu]
    for mid in FEATURES:
        assert app.lifecycle.get_state(mid) == "enabled"
        assert mid in reg.features
    assert "整点报时(开关)" in labels
    assert "查天气" in labels
    assert "待办清单" in labels
    assert "系统状态" in labels
    assert "模组打包 / 导入" in labels
    await app.stop()


async def test_clock_hour_text_and_toggle(feats_env):
    app, _plugins, win = feats_env
    await app.start(_plugins)
    clock = _ns("feature.clock")
    assert "正午" in clock["_hour_text"](12)
    assert "夜" in clock["_hour_text"](23)
    state = app.registry.use("state")
    state.change("clock.enabled", True)
    for label, cb in win.feature_menu:
        if "整点报时" in label:
            cb()   # 关
            assert state.get("clock.enabled") is False
            cb()   # 开
            assert state.get("clock.enabled") is True
    await app.stop()


async def test_weather_pure_parsers(feats_env):
    app, _plugins, _win = feats_env
    await app.start(_plugins)
    w = _ns("feature.weather")
    r = w["parse_wttr"]({
        "current_condition": [{"temp_C": "31", "weatherDesc": [{"value": "Sunny"}]}],
        "nearest_area": [{"areaName": [{"value": "Beijing"}]}],
    })
    assert r["ok"] and r["city"] == "Beijing" and r["temp"] == 31.0, r
    assert not w["parse_wttr"]({"current_condition": []})["ok"]
    r3 = w["parse_open_meteo"](
        {"city": "上海"},
        {"current_weather": {"temperature": 5.5, "weathercode": 61}},
    )
    assert r3["ok"] and r3["desc"] == "小雨" and r3["temp"] == 5.5, r3
    assert "网络不太" in w["weather_text"]({"ok": False})
    assert "带伞" in w["weather_text"](r3)          # 下雨 → 提醒带伞
    assert "冷" in w["weather_text"](r3)             # 5.5℃ → 保暖
    assert "热" in w["weather_text"]({"ok": True, "city": "", "temp": 35, "desc": "晴"})
    await app.stop()


async def test_weather_disable_drops_late_callback(feats_env):
    """B2 回归: 禁用时断开 done + wait, 迟到的线程回调不落到已卸载实例。"""
    app, _plugins, win = feats_env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    w = _ns("feature.weather")
    inst = mm.instances["feature.weather"]

    def _slow_fetch():
        time.sleep(0.6)
        return {"ok": True, "city": "测试", "temp": 20, "desc": "晴"}

    orig = w["fetch_weather"]
    w["fetch_weather"] = _slow_fetch
    try:
        inst._query()                      # 起慢线程
        assert inst._worker is not None
        win.bubble._full = ""              # 清掉"我看一眼天"
        await mm.set_enabled("feature.weather", False)   # 禁用 → disconnect+wait
        qapp_process()
        assert win.bubble._full == ""      # 迟到回调被丢弃
        assert mm.instances.get("feature.weather") is None
        await mm.set_enabled("feature.weather", True)    # 复活
        assert mm.instances.get("feature.weather") is not None
    finally:
        w["fetch_weather"] = orig
    await app.stop()


def qapp_process():
    QApplication.instance().processEvents()


async def test_todo_window_and_persistence(feats_env):
    app, _plugins, win = feats_env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    state = app.registry.use("state")
    state.change("todo.items", [{"text": "写报告", "done": False}, {"text": "买猫粮", "done": True}])
    state.change("todo.last_day", "")
    inst = mm.instances["feature.todo"]
    inst._open()
    todo_win = mm.feature_data("feature.todo")["win"]
    assert todo_win.list.count() == 2
    todo_win.input.setText("喂影")
    todo_win._add()
    assert len(state.get("todo.items")) == 3
    todo_win.list.item(0).setSelected(True)
    todo_win._toggle_selected()
    assert state.get("todo.items")[0]["done"] is True
    todo_win._clear_done()
    assert len(state.get("todo.items")) == 1
    todo_win.list.item(0).setSelected(True)
    todo_win._del_selected()
    assert state.get("todo.items") == []
    todo_win.close()

    # 每日播报: 当天只报一次
    state.change("todo.items", [{"text": "写周报", "done": False}])
    state.change("todo.last_day", "")
    inst._daily_report()
    assert "1 件事" in win.bubble._full
    win.bubble._full = ""
    inst._daily_report()
    assert win.bubble._full == ""
    await app.stop()


async def test_sysmon_sample_and_text(feats_env):
    app, _plugins, _win = feats_env
    await app.start(_plugins)
    s = _ns("feature.sysmon")
    r = s["sample_system"]()
    assert r["ok"] is True                  # 本机 Windows, 真实采样
    t = s["sysmon_text"]({"ok": True, "cpu": 95, "mem": 40, "total_gb": 32})
    assert "CPU" in t and "撑不住" in t
    assert "仅支持 Windows" in s["sysmon_text"]({"ok": False})
    await app.stop()


async def test_packer_window_lists_mods(feats_env):
    app, _plugins, _win = feats_env
    await app.start(_plugins)
    mm = app.registry.use("module_manager")
    p = _ns("feature.packer")
    assert p["_mod_type"](mm.registry.features["feature.packer"]) == "feature"
    inst = mm.instances["feature.todo"]
    pw = p["PackerWindow"](inst.ctx)        # 用任一 FeatureContext 构造窗口
    assert pw.list.count() == len(mm.registry.all_mods)
    pw.close()
    await app.stop()
