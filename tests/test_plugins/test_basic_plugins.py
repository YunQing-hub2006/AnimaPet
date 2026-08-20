# -*- coding: utf-8 -*-
"""config/state/actions 三基础插件的内核协作测试。"""
import asyncio

import pytest

from anima.core import App
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.state import StatePlugin, StateService
from anima.plugins.actions import ActionsPlugin, ActionRegistry


@pytest.fixture
def app(tmp_path, monkeypatch):
    # 数据文件重定向到临时目录, 避免测试串扰真实 data/
    from anima.utils import jsonio, paths
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({
        str(tmp_path / "config.json"), str(tmp_path / "state.json")}))
    return App()


async def test_config_plugin_provides_service(app):
    await app.start([ConfigPlugin()])
    cfg = app.registry.use("config")
    assert isinstance(cfg, ConfigService)
    assert cfg.get("api.model") == "deepseek-v4-flash"
    assert cfg.get("no.such.key", "fallback") == "fallback"
    assert cfg.get("") is cfg.data  # 空 key 返回根
    await app.stop()


async def test_config_set_dotpath_and_persist(app, tmp_path):
    target = tmp_path / "config.json"
    await app.start([ConfigPlugin()])
    cfg = app.registry.use("config")
    cfg.set("window.size", "large")
    cfg.set("mods.enabled.feature.hello", False)
    assert cfg.get("window.size") == "large"
    cfg.save()
    import json
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk["window"]["size"] == "large"
    await app.stop()


async def test_state_change_funnel_broadcasts(app):
    received = []
    await app.start([StatePlugin(), ConfigPlugin()])
    app.bus.subscribe("state.changed", lambda d: received.append(d))
    st = app.registry.use("state")
    st.change("affinity", 7)
    assert st.get("affinity") == 7
    assert received == [{"key": "affinity", "value": 7}]
    # dict 协议走同一个漏斗
    st["petted_count"] = 3
    assert st["petted_count"] == 3
    assert received[-1] == {"key": "petted_count", "value": 3}
    await app.stop()


async def test_state_inc_missing_key_starts_from_zero(app):
    await app.start([StatePlugin(), ConfigPlugin()])
    st = app.registry.use("state")
    st.inc("fresh_counter", 5)
    assert st.get("fresh_counter") == 5
    st.inc("fresh_counter")
    assert st.get("fresh_counter") == 6
    await app.stop()


async def test_actions_builtin_registered_and_fire(app):
    received = []
    await app.start([ActionsPlugin(), StatePlugin(), ConfigPlugin()])
    actions = app.registry.use("actions")
    assert isinstance(actions, ActionRegistry)
    assert "state_inc" in actions.names()
    st = app.registry.use("state")
    app.bus.subscribe("state.changed", lambda d: received.append(d))

    inc = actions.get("state_inc")
    inc({"key": "affinity", "delta": 10}, None, None)
    assert st.get("affinity") == 10

    set_fn = actions.get("state_set")
    set_fn({"key": "affinity", "value": 99}, None, None)
    assert st.get("affinity") == 99

    emit_fn = actions.get("emit")
    emit_fn({"event": "custom.ping", "data": {"x": 1}}, None, None)
    assert received[-1] == {"key": "affinity", "value": 99}
    await app.stop()


async def test_actions_disable_removes_builtins(app):
    await app.start([ActionsPlugin(), StatePlugin(), ConfigPlugin()])
    actions = app.registry.use("actions")
    await app.lifecycle.disable("actions")
    assert "state_inc" not in actions.names()
    await app.stop()


async def test_topo_order_fixes_reversed_registration(app):
    # 故意乱序传入, 内核应按 dependencies 排好加载顺序
    await app.start([ActionsPlugin(), StatePlugin(), ConfigPlugin()])
    order = app.lifecycle._load_order
    assert order.index("config") < order.index("state") < order.index("actions")
    await app.stop()
