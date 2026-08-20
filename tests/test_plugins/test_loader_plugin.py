# -*- coding: utf-8 -*-
"""loader 插件测试: 扫描->enabled 分流->provide("mods")。"""
import json
import os

import pytest

from anima.core import App
from anima.plugins.config import ConfigPlugin
from anima.plugins.loader import LoaderPlugin
from anima.mods.registry import Registry


@pytest.fixture
def pet_app(tmp_path, monkeypatch):
    """带临时 mods/ 与 data/ 的 App, 装好 config + loader。"""
    from anima.utils import jsonio, paths
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", os.path.normpath(str(tmp_path)))

    (mods_dir / "card.ying").mkdir()
    (mods_dir / "card.ying" / "manifest.json").write_text(json.dumps({
        "id": "card.ying", "type": "card", "version": "1.0.0", "name": "影",
        "system_prompt": "人设", "idle_anim": "", "talk_anim": "",
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "ui.default").mkdir()
    (mods_dir / "ui.default" / "manifest.json").write_text(json.dumps({
        "id": "ui.default", "type": "ui", "name": "默认", "theme": {},
    }, ensure_ascii=False), encoding="utf-8")

    app = App()
    return app, mods_dir


async def test_loader_provides_registry(pet_app):
    app, _ = pet_app
    await app.start([LoaderPlugin(), ConfigPlugin()])
    reg = app.registry.use("mods")
    assert isinstance(reg, Registry)
    assert reg.characters.get("card.ying")
    assert reg.uis.get("ui.default")
    await app.stop()


async def test_loader_respects_enabled_map(pet_app):
    app, _ = pet_app
    cfg = app.registry  # not started yet; enabled map written pre-start
    # 预写禁用 ui.default
    from anima.utils import jsonio, paths
    jsonio.save(paths.CONFIG_PATH, {"mods": {"enabled": {"ui.default": False}}})
    await app.start([LoaderPlugin(), ConfigPlugin()])
    reg = app.registry.use("mods")
    assert reg.uis.get("ui.default") is None      # 禁用: 不收纳
    assert reg.characters.get("card.ying")        # 启用
    assert any(m.id == "ui.default" for m in reg.all_mods)  # 全量仍含
    await app.stop()


async def test_rescan_broadcasts_event(pet_app):
    app, mods_dir = pet_app
    received = []
    loader_plugin = LoaderPlugin()
    await app.start([loader_plugin, ConfigPlugin()])
    app.bus.subscribe("mods.reloaded", lambda d: received.append(d))
    reg = app.registry.use("mods")

    # 运行中新增一个皮肤模组目录 -> rescan 应收纳
    (mods_dir / "ui.dark").mkdir()
    (mods_dir / "ui.dark" / "manifest.json").write_text(json.dumps({
        "id": "ui.dark", "type": "ui", "name": "暗色", "theme": {}}), encoding="utf-8")
    loader_plugin.rescan()
    assert reg.uis.get("ui.dark")
    assert received and "errors" in received[0]
    await app.stop()


async def test_scan_reports_bad_mod_but_keeps_going(pet_app):
    app, mods_dir = pet_app
    (mods_dir / "broken").mkdir()
    (mods_dir / "broken" / "manifest.json").write_text("not json", encoding="utf-8")
    await app.start([LoaderPlugin(), ConfigPlugin()])
    reg = app.registry.use("mods")
    assert reg.characters.get("card.ying")          # 坏模组不拖垮全局
    assert any(name == "broken" for name, _ in reg.errors)
    await app.stop()
