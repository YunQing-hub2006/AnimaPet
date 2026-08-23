# -*- coding: utf-8 -*-
"""charcard 编辑器离屏测试: 管理器打开 / 四页签写回路由 / 新建向导删除干净。

AnimaPet 等价体(自 YingPet-v4 tests/test_charcard.py 改写): 数据源从
FeatureContext 改为 module_manager 服务; 保存动作经 anima.models 整体预检;
重扫走 mm.rescan()(_wait_rescan 模式)。
"""
import json
import os
import shutil

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

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


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def charcard_env(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    card = mods_dir / "card.ying"
    card.mkdir()
    (card / "anims" / "idle" / "frames").mkdir(parents=True)
    (card / "anims" / "talk" / "frames").mkdir(parents=True)
    (card / "manifest.json").write_text(json.dumps({
        "id": "card.ying", "type": "card", "version": "1.0.0", "name": "影",
        "description": "原描述", "system_prompt": "原人设",
        "idle_anim": "idle", "talk_anim": "talk",
    }, ensure_ascii=False), encoding="utf-8")
    (card / "emotes.json").write_text(json.dumps({
        "emotes": {"default": {"name": "平时", "image": "", "anim": "",
                               "hold_ms": 4000, "lines": ["原台词"]}},
    }, ensure_ascii=False), encoding="utf-8")
    (card / "idle.json").write_text(json.dumps({
        "interval_min": 30, "interval_max": 42,
        "lines": {"default": ["原空闲"]},
    }, ensure_ascii=False), encoding="utf-8")
    (card / "behaviors.json").write_text(json.dumps({
        "rules": [{"on": "pet.petted", "cooldown": 2, "then": [{"say": "原规则"}]}],
    }, ensure_ascii=False), encoding="utf-8")

    fcard = mods_dir / "feature.charcard"
    fcard.mkdir()
    (fcard / "manifest.json").write_text(json.dumps({
        "id": "feature.charcard", "type": "feature", "version": "1.0.0",
        "name": "角色卡管理器", "main": "plugin.py"}, ensure_ascii=False), encoding="utf-8")
    (fcard / "plugin.py").write_text(
        '''class Feature:
    id = 'feature.charcard'
    name = '角色卡管理器'

    def on_load(self, ctx):
        ctx.add_menu_action('角色卡管理器…', lambda: None)
''', encoding="utf-8")

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    cfg, st = ConfigService(), StateService()
    cfg.load()
    st.load()
    reg = Registry()
    actions = ActionRegistry()
    app = App()
    win = PetWindow(reg, app.bus, cfg, st, actions=actions)
    bridge = BridgePlugin(win)
    mm_plugin = ModuleManagerPlugin()
    plugins = [ConfigPlugin(cfg), StatePlugin(st), ActionsPlugin(actions),
               LoaderPlugin(reg), RuleEnginePlugin(), bridge, mm_plugin]
    return app, plugins, win, mm_plugin, mods_dir, card


async def start(env):
    app, plugins, *_ = env
    await app.start(plugins)
    return app.registry.use("module_manager")


def _backup(card):
    return {name: json.loads((card / name).read_text(encoding="utf-8"))
            for name in ("manifest.json", "emotes.json", "idle.json", "behaviors.json")}


def _restore(card, backup):
    for name, data in backup.items():
        (card / name).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


async def test_dialog_open_lists_card_and_internal_anims(charcard_env):
    app, _, _, _, _, _ = charcard_env
    mm = await start(charcard_env)
    from anima.window.dialogs.charcard.dialog import CardManagerDialog
    dlg = CardManagerDialog(mm)
    dlg._reload_chars("card.ying")
    assert dlg.current_id == "card.ying"
    assert dlg.listw.count() == 1
    idle_items = [dlg.cmb_idle.itemText(i) for i in range(dlg.cmb_idle.count())]
    assert any("卡内 · idle" in t for t in idle_items), idle_items
    assert dlg.cmb_idle.currentData() == "card.ying:idle"
    await app.stop()


async def test_writeback_routes_to_card_files(charcard_env, qapp):
    app, _, _, _, _, card = charcard_env
    mm = await start(charcard_env)
    orig = _backup(card)
    try:
        from anima.window.dialogs.charcard.dialog import CardManagerDialog
        dlg = CardManagerDialog(mm)
        dlg._reload_chars("card.ying")

        # 2a) 人设 → manifest.json
        dlg.ed_desc.setText("测试描述-anima")
        dlg._save_persona()
        mf = json.loads((card / "manifest.json").read_text(encoding="utf-8"))
        assert mf.get("description") == "测试描述-anima"

        # 2b) 台词 → idle.json
        dlg.cmb_idle_pack.setCurrentIndex(0)
        dlg._on_idle_pack_changed()
        secs = [dlg.cmb_idle_section.itemText(i)
                for i in range(dlg.cmb_idle_section.count())]
        assert "default" in secs, secs
        dlg.ed_idle_lines.setPlainText("测试台词一\n测试台词二")
        dlg._save_idle()
        idle_raw = json.loads((card / "idle.json").read_text(encoding="utf-8"))
        assert "测试台词一" in (idle_raw.get("lines", {}).get("default") or []), idle_raw

        # 2c) 行为 → behaviors.json (表单: on/when/cooldown/then-JSON)
        dlg.ed_rule_on.setText("pet.petted")
        dlg.ed_rule_when.setText("event.affinity >= 1")
        dlg.ed_rule_cooldown.setText("5")
        dlg.ed_rule_then.setPlainText('[{"say": "@idle.this.default"}]')
        dlg._add_rule()
        dlg._save_beh()
        beh_raw = json.loads((card / "behaviors.json").read_text(encoding="utf-8"))
        assert any(r.get("cooldown") == 5 and r.get("when") == "event.affinity >= 1"
                   for r in beh_raw.get("rules", [])), beh_raw

        # 2d) 表情 → emotes.json
        found = False
        for row in range(dlg.emote_list.count()):
            if str(dlg.emote_list.item(row).data(0x0100)) == "default":
                dlg.emote_list.setCurrentRow(row)
                found = True
                break
        assert found, "default 表情不在列表"
        dlg.ed_emo_lines.setPlainText("测试表情台词")
        dlg._save_emote()
        emo_raw = json.loads((card / "emotes.json").read_text(encoding="utf-8"))
        assert emo_raw.get("emotes", {}).get("default", {}).get("lines") == ["测试表情台词"], emo_raw
    finally:
        _restore(card, orig)
        mm.rescan()
    await app.stop()


async def test_wizard_creates_hotloads_and_deletes(charcard_env):
    app, _, _, _, mods_dir, card = charcard_env
    mm = await start(charcard_env)
    orig = _backup(card)
    card2 = mods_dir / "card.test_card"
    try:
        from anima.window.dialogs.charcard.wizard import NewCardWizard
        wiz = NewCardWizard(mm)
        wiz.ed_id.setText("test_card")
        wiz.ed_name.setText("测试角色")
        wiz.ed_prompt.setPlainText("你是测试角色。")
        assert wiz._validate_step1()
        wiz._step = 2
        wiz._finish()
        assert wiz.created_id == "card.test_card"
        for f in ("manifest.json", "emotes.json", "idle.json", "behaviors.json"):
            assert (card2 / f).is_file(), f
        assert mm.registry.character("card.test_card") is not None
        assert mm.registry.behaviors.get("card.test_card:behaviors") is not None

        # 删除: 还原配置 → 删文件夹 → 重扫不可见
        mm.config.set("mods.character", "")
        mm.config.save()
        shutil.rmtree(card2)
        mm.rescan()
        assert mm.registry.character("card.test_card") is None
        assert mm.registry.character("card.ying") is not None
    finally:
        _restore(card, orig)
        mm.rescan()
    await app.stop()


async def test_charcard_feature_managed_by_module_manager(charcard_env):
    """方案 A: feature.charcard 是受管功能模组, 可被总管理器禁用/再启用。"""
    app, _, win, _, _, _ = charcard_env
    mm = await start(charcard_env)
    assert "feature.charcard" in mm.instances
    assert any("角色卡管理器" in label for label, _ in win.feature_menu)
    await mm.set_enabled("feature.charcard", False)
    assert "feature.charcard" not in mm.instances
    assert not any("角色卡管理器" in label for label, _ in win.feature_menu)
    await mm.set_enabled("feature.charcard", True)
    assert "feature.charcard" in mm.instances
    assert any("角色卡管理器" in label for label, _ in win.feature_menu)
    await app.stop()
