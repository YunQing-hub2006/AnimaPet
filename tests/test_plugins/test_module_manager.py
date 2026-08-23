# -*- coding: utf-8 -*-
"""module_manager 专项测试: 运行时启停 / zip-slip / 冲突改名 / 删除复活 / 新建模板。

对账语义(与 YingPet 一致): feature 禁用 = 完整卸载(副作用回滚、菜单移除),
再启用 = 全新实例重新 on_load —— 私有数据经 feature_data 跨周期保留。
"""
import asyncio
import json
import os
import zipfile

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

FEATURE_DEMO_CODE = '''# -*- coding: utf-8 -*-
class Feature:
    id = "feature.demo"
    name = "演示"

    def on_load(self, ctx):
        self.ctx = ctx
        self.events = []
        ctx.on("demo.ping", self._ping)
        ctx.add_menu_action("Demo 菜单", self._menu)
        ctx.data["hello"] = "world"

    def _ping(self, payload):
        self.events.append(("ping", payload))

    def _menu(self):
        self.events.append(("menu", None))

    def on_disable(self):
        self.events.append(("disable", None))
'''


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def mm_env(tmp_path, monkeypatch, qapp):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    (mods_dir / "ui.default").mkdir()
    (mods_dir / "ui.default" / "manifest.json").write_text(json.dumps({
        "id": "ui.default", "type": "ui", "name": "默认", "theme": {}}), encoding="utf-8")
    (mods_dir / "card.ying").mkdir()
    (mods_dir / "card.ying" / "manifest.json").write_text(json.dumps({
        "id": "card.ying", "type": "card", "version": "1.0.0", "name": "影",
        "system_prompt": "原人设", "idle_anim": "", "talk_anim": "",
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "feature.demo").mkdir()
    (mods_dir / "feature.demo" / "manifest.json").write_text(json.dumps({
        "id": "feature.demo", "type": "feature", "version": "1.0.0",
        "name": "演示", "main": "plugin.py"}), encoding="utf-8")
    (mods_dir / "feature.demo" / "plugin.py").write_text(FEATURE_DEMO_CODE, encoding="utf-8")

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
    return app, plugins, win, bridge, mm_plugin, mods_dir


async def start(mm_env):
    app, plugins, *_ = mm_env
    await app.start(plugins)
    return app.registry.use("module_manager")


def make_mod_zip(tmp_path, mod_id, evil=False, plugin_code="pass\n"):
    d = tmp_path / "pack" / mod_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "id": mod_id, "type": "feature", "version": "1.0.0", "name": mod_id,
        "main": "plugin.py"}), encoding="utf-8")
    (d / "plugin.py").write_text(plugin_code, encoding="utf-8")
    zpath = tmp_path / (mod_id + ".zip")
    with zipfile.ZipFile(zpath, "w") as zf:
        for f in d.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(d.parent).as_posix())
        if evil:
            zf.writestr("../evil.txt", "boom")
    return str(zpath)


async def test_feature_auto_enabled_and_menu_registered(mm_env):
    app, _, win, bridge, _, _ = mm_env
    mm = await start(mm_env)
    assert mm.is_enabled("feature.demo")
    assert app.lifecycle.get_state("feature.demo") == "enabled"
    assert mm.instances.get("feature.demo") is not None
    assert [label for label, _ in win.feature_menu] == ["模组管理", "设置 (API / 人设)", "Demo 菜单"]
    # 私有数据容器跨周期可写
    inst = mm.instances["feature.demo"]
    assert mm.feature_data("feature.demo")["hello"] == "world"
    # 事件订阅生效
    app.bus.emit("demo.ping", {"x": 1})
    assert inst.events == [("ping", {"x": 1})]
    await app.stop()


async def test_feature_runtime_disable_enable(mm_env):
    app, _, win, _, _, _ = mm_env
    mm = await start(mm_env)
    inst = mm.instances["feature.demo"]

    await mm.set_enabled("feature.demo", False)
    assert app.lifecycle.get_state("feature.demo") == "unloaded"   # 完整卸载
    assert [label for label, _ in win.feature_menu] == ["模组管理", "设置 (API / 人设)"]  # 菜单已移除
    assert ("disable", None) in inst.events
    assert mm.instances.get("feature.demo") is None
    assert mm.is_enabled("feature.demo") is False

    await mm.set_enabled("feature.demo", True)
    assert app.lifecycle.get_state("feature.demo") == "enabled"    # 全新实例
    new_inst = mm.instances["feature.demo"]
    assert new_inst is not None and new_inst is not inst
    assert [label for label, _ in win.feature_menu] == ["模组管理", "设置 (API / 人设)", "Demo 菜单"]
    assert mm.feature_data("feature.demo")["hello"] == "world"     # 数据跨周期保留
    await app.stop()


async def test_data_mod_toggle_rebuilds_registry(mm_env):
    app, _, _, _, _, _ = mm_env
    mm = await start(mm_env)
    assert mm.registry.uis.get("ui.default") is not None
    await mm.set_enabled("ui.default", False)
    assert mm.registry.uis.get("ui.default") is None
    assert any(m.id == "ui.default" for m in mm.registry.all_mods)  # 全量仍在
    await mm.set_enabled("ui.default", True)
    assert mm.registry.uis.get("ui.default") is not None
    await app.stop()


async def test_import_zip_slip_rejected(mm_env):
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    tmp_path = mods_dir.parent
    zpath = make_mod_zip(tmp_path, "feature.evil", evil=True)
    before = sorted(os.listdir(str(mods_dir)))
    with pytest.raises(ValueError):
        await mm.import_zip(zpath)
    assert sorted(os.listdir(str(mods_dir))) == before          # 目录未被动
    assert not (tmp_path / "evil.txt").exists()                  # 穿越未发生
    await app.stop()


async def test_import_zip_conflict_rename(mm_env):
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    zpath = make_mod_zip(mods_dir.parent, "feature.fresh")
    new_id, _ = await mm.import_zip(zpath)
    assert new_id == "feature.fresh"
    # 再次导入同名包 → 自动改名 id_2 并回写 manifest
    new_id2, dest2 = await mm.import_zip(zpath)
    assert new_id2 == "feature.fresh_2"
    manifest = json.loads(open(os.path.join(dest2, "manifest.json"), encoding="utf-8").read())
    assert manifest["id"] == "feature.fresh_2"
    ids = {m.id for m in mm.registry.all_mods}
    assert "feature.fresh" in ids and "feature.fresh_2" in ids
    await app.stop()


async def test_delete_mod_then_revive(mm_env):
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    zpath = make_mod_zip(mods_dir.parent, "feature.cycle")
    new_id, dest = await mm.import_zip(zpath)
    assert app.lifecycle.get_state(new_id) == "enabled"

    await mm.delete_mod(new_id)
    assert app.lifecycle.get_state(new_id) == "unloaded"
    assert not os.path.isdir(dest)
    assert all(m.id != new_id for m in mm.registry.all_mods)

    # 删除复活: 同包重新导入, 完好如初
    new_id2, _ = await mm.import_zip(zpath)
    assert new_id2 == "feature.cycle"
    assert app.lifecycle.get_state(new_id2) == "enabled"
    await app.stop()


async def test_create_feature_mod_template(mm_env):
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    mid = await mm.create_feature_mod("greet", "问候")
    assert mid == "feature.greet"
    assert (mods_dir / "feature.greet" / "plugin.py").exists()
    assert app.lifecycle.get_state("feature.greet") == "enabled"
    inst = mm.instances.get("feature.greet")
    assert inst is not None
    assert mm.is_enabled("feature.greet")
    await app.stop()


async def test_create_feature_mod_bad_id(mm_env):
    app, _, _, _, _, _ = mm_env
    mm = await start(mm_env)
    with pytest.raises(ValueError):
        await mm.create_feature_mod("../evil", "x")
    await app.stop()


async def test_export_zip(mm_env):
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    dest = str(mods_dir.parent / "out.zip")
    n = mm.export_zip("ui.default", dest)
    assert n >= 1
    with zipfile.ZipFile(dest) as zf:
        assert any("manifest.json" in name for name in zf.namelist())
    await app.stop()


async def test_list_mods_summary(mm_env):
    app, _, _, _, _, _ = mm_env
    mm = await start(mm_env)
    items = mm.list_mods()
    assert any(i["id"] == "feature.demo" and i["feature"] and i["enabled"] for i in items)
    assert any(i["id"] == "ui.default" and i["type"] == "ui" for i in items)
    await app.stop()


async def test_rescan_sync_on_kernel_thread(mm_env):
    """内核线程(有运行循环)上 rescan() 同步执行、返回 None 并立即重建注册表。"""
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    (mods_dir / "ui.dark").mkdir()
    (mods_dir / "ui.dark" / "manifest.json").write_text(json.dumps({
        "id": "ui.dark", "type": "ui", "name": "暗色", "theme": {}}), encoding="utf-8")
    assert mm.rescan() is None
    assert mm.registry.uis.get("ui.dark") is not None   # 已同步生效
    await app.stop()


async def test_settings_dialog_saves_config_and_char_prompt(mm_env, qapp):
    """SettingsDialog: API 配置写 config 服务, 人设写回角色卡 manifest。"""
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    from anima.window.dialogs.settings import SettingsDialog
    dlg = SettingsDialog(mm)
    assert dlg._current_char() is not None and dlg._current_char().id == "card.ying"
    dlg.ed_key.setText("sk-test")
    dlg.ed_base.setText("https://example.com")
    dlg.ed_model.setCurrentText("model-x")
    dlg.ed_temp.setText("1.2")
    dlg.ed_effort.setCurrentIndex(2)          # medium
    dlg.ed_prompt.setPlainText("新人设")
    dlg._save()
    assert mm.config.get("api.api_key") == "sk-test"
    assert mm.config.get("api.base_url") == "https://example.com"
    assert mm.config.get("api.temperature") == 1.2
    assert mm.config.get("api.reasoning_effort") == "medium"
    manifest = json.loads((mods_dir / "card.ying" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_prompt"] == "新人设"
    await app.stop()


async def test_mods_dialog_delete_mod(mm_env, qapp, monkeypatch):
    """ModsDialog 删除功能: 确认后 feature 先卸载、文件夹删除、注册表移除。"""
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    from PyQt6.QtWidgets import QMessageBox
    from anima.window.dialogs.modmanager import ModsDialog
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (asked.append(a) or QMessageBox.StandardButton.Yes)))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = ModsDialog(mm)
    assert any(mid == "feature.demo" for mid, _cb, _it in dlg._rows)
    dlg._delete_mod("feature.demo")
    assert asked                                   # 删除前有确认框
    await asyncio.sleep(0)                          # fire 排队的 delete 完成
    assert all(m.id != "feature.demo" for m in mm.registry.all_mods)
    assert not (mods_dir / "feature.demo").exists()  # 文件夹已删
    assert app.lifecycle.get_state("feature.demo") == "unloaded"
    await app.stop()


async def test_mods_dialog_delete_cancelled(mm_env, qapp, monkeypatch):
    """删除确认选 No → 模组原样保留。"""
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    from PyQt6.QtWidgets import QMessageBox
    from anima.window.dialogs.modmanager import ModsDialog
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg = ModsDialog(mm)
    dlg._delete_mod("feature.demo")
    await asyncio.sleep(0)
    assert any(m.id == "feature.demo" for m in mm.registry.all_mods)
    assert (mods_dir / "feature.demo").exists()
    await app.stop()


async def test_mods_dialog_new_feature_entry(mm_env, qapp, monkeypatch):
    """「新建…→ 新建功能模组…」: 生成模板、自动启用并进入总管理器列表。"""
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    from anima.window.dialogs.modmanager import ModsDialog, NewFeatureModDialog
    monkeypatch.setattr(
        __import__("anima.window.dialogs.modmanager", fromlist=["QMessageBox"]).QMessageBox,
        "warning", staticmethod(lambda *a, **k: None))
    dlg = ModsDialog(mm)
    assert "新建功能模组…" in [a.text() for a in dlg.menu_new.actions()]
    nd = NewFeatureModDialog(mm)
    nd.ed_id.setText("my_feature")
    nd.ed_name.setText("我的功能")
    nd._save()
    await asyncio.sleep(0.05)
    assert nd.created_id == "feature.my_feature"
    assert (mods_dir / "feature.my_feature" / "manifest.json").exists()
    assert mm.instances.get("feature.my_feature") is not None
    await app.stop()


async def test_export_log_service_and_dialog_buttons(mm_env, tmp_path, monkeypatch):
    """导出日志: 服务复制 pet.log; 模组管理对话框有导出/打开日志按钮。"""
    app, _, _, _, _, _ = mm_env
    mm = await start(mm_env)
    log_path = tmp_path / "pet.log"
    log_path.write_text("line1\n", encoding="utf-8")
    monkeypatch.setattr(paths, "LOG_PATH", str(log_path))
    dest = tmp_path / "out.log"
    assert mm.export_log(str(dest)) == str(dest)
    assert dest.read_text(encoding="utf-8") == "line1\n"
    from anima.window.dialogs.modmanager import ModsDialog
    dlg = ModsDialog(mm)
    assert dlg.btn_export_log.text() == "导出日志…"
    assert dlg.btn_open_log.text() == "打开日志文件夹"
    await app.stop()
