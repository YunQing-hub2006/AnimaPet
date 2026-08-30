# -*- coding: utf-8 -*-
"""皮肤工坊测试: 取色→保存生成 ui.* 模组 / 冲突拒绝 / 现有皮肤作为起点。"""
import json
import os

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from tests.test_plugins.test_module_manager import mm_env, qapp, start  # noqa: F401


async def test_skinmaker_saves_ui_mod_and_applies(mm_env, qapp):  # noqa: F811
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    from anima.window.dialogs.skinmaker import SkinMakerDialog
    dlg = SkinMakerDialog(mm)
    dlg.ed_id.setText("my_night")
    dlg.ed_name.setText("我的夜色")
    dlg._colors["accent"] = "#3366cc"
    dlg._colors["bg_window"] = "#101020"
    dlg._save()
    assert dlg.created_id == "ui.my_night"
    mf = json.load(open(os.path.join(mods_dir, "ui.my_night", "manifest.json"),
                        encoding="utf-8"))
    assert mf["type"] == "ui" and mf["name"] == "我的夜色"
    assert mf["theme"]["accent"] == "#3366cc"
    assert mm.config.get("mods.ui") == "ui.my_night"     # 默认勾了"保存后立即换上"
    # 热重载后进注册表, 与手写皮肤同构
    mm.rescan()
    skin = mm.registry.ui("ui.my_night")
    assert skin is not None and skin.theme["bg_window"] == "#101020"
    await app.stop()


async def test_skinmaker_rejects_conflict_and_bad_id(mm_env, qapp, monkeypatch):  # noqa: F811
    app, _, _, _, _, mods_dir = mm_env
    mm = await start(mm_env)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a[1]) or None))
    from anima.window.dialogs.skinmaker import SkinMakerDialog
    dlg = SkinMakerDialog(mm)

    dlg.ed_id.setText("坏 ID!")
    dlg._save()
    assert dlg.created_id == "" and "id 不合法" in warned

    (mods_dir / "ui.taken").mkdir()
    dlg.ed_id.setText("taken")
    dlg._save()
    assert dlg.created_id == "" and "id 冲突" in warned
    assert not (mods_dir / "ui.taken" / "manifest.json").exists()
    await app.stop()


async def test_skinmaker_lists_skins_as_base(mm_env, qapp):  # noqa: F811
    app, _, _, _, _, _ = mm_env
    mm = await start(mm_env)   # mm_env 里有 ui.default
    from anima.window.dialogs.skinmaker import SkinMakerDialog
    dlg = SkinMakerDialog(mm)
    labels = [dlg.cmb_base.itemText(i) for i in range(dlg.cmb_base.count())]
    datas = [str(dlg.cmb_base.itemData(i) or "") for i in range(dlg.cmb_base.count())]
    assert any("ui.default" in d for d in datas), labels
    # 载入现有皮肤: 配色切换为该皮肤 theme, 不改盘
    idx = dlg.cmb_base.findData("ui.default")
    dlg.cmb_base.setCurrentIndex(idx)
    dlg._load_base()
    assert isinstance(dlg._colors, dict) and dlg._colors.get("accent")
    await app.stop()
