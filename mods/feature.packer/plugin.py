# -*- coding: utf-8 -*-
"""模组打包/导入导出。自 YingPet-v4 feature.packer 平移:

- 导出: 任意模组 → <id>.zip(保留文件夹结构), 用于分享/备份
- 导入: 选择 zip → 校验 manifest + 防 Zip Slip → 装入 mods/ → 热重载
- id 冲突时自动改名(id、id_2、id_3…), 绝不覆盖已有模组

差异: 纯函数核心(safe_zip_members/read_manifest_from_zip/unique_target_dir/
export_mod/import_mod_zip)已提取到 anima.mods.packer 供数据层复用, 这里只保留
界面 + 接线; 类型显示改用 isinstance 判定(模组对象无 .type 字段)。
"""
import os

from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from anima.mods import loader as mods_loader
from anima.mods import packer
from anima.utils import log, paths

_log = log.get("feature.packer")

STYLE = (
    "QWidget { background: #ffffff; color: #111111; font-family: 'Microsoft YaHei'; }"
    "QLabel { background: transparent; }"
    "QListWidget { background: #ffffff; border: 1px solid #c0c0c0; }"
    "QListWidget::item { padding: 3px; }"
    "QListWidget::item:selected { background: #d6e4ff; color: #000000; }"
    "QPushButton { background: #f2f2f2; border: 1px solid #b0b0b0;"
    " border-radius: 3px; padding: 5px 14px; }"
    "QPushButton:hover { background: #e2e2e2; }"
)


def _mod_type(m):
    """从模组对象类型判定 type(模组对象无 .type 字段)。"""
    for cls, t in ((mods_loader.CharacterMod, "character"), (mods_loader.AnimMod, "anim"),
                   (mods_loader.EmoteDef, "emote"), (mods_loader.IdlePack, "idle"),
                   (mods_loader.BehaviorMod, "behavior"), (mods_loader.FeatureMod, "feature"),
                   (mods_loader.UiMod, "ui")):
        if isinstance(m, cls):
            return t
    return m.id.split(".")[0] if "." in m.id else "?"


class PackerWindow(QWidget):
    def __init__(self, ctx):
        super().__init__(None)
        self.ctx = ctx
        self.setWindowTitle("模组打包 / 导入")
        self.setStyleSheet(STYLE)
        self.resize(460, 440)
        layout = QVBoxLayout(self)

        title = QLabel("模组打包 / 导入")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        tip = QLabel("导出: 选中模组 → 存为 zip(分享给别人)。\n"
                     "导入: 选 zip → 自动装入 mods/ 并热重载(重名自动改名)。")
        tip.setStyleSheet("color: #555555;")
        layout.addWidget(tip)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        btn_export = QPushButton("导出选中")
        btn_export.clicked.connect(self._export)
        row.addWidget(btn_export)
        btn_import = QPushButton("导入模组包")
        btn_import.clicked.connect(self._import)
        row.addWidget(btn_import)
        btn_folder = QPushButton("打开 mods 目录")
        btn_folder.clicked.connect(lambda: self.ctx.open_path(paths.MODS_DIR))
        row.addWidget(btn_folder)
        layout.addLayout(row)

        self._reload_list()

    def _reload_list(self):
        self.list.clear()
        try:
            mods = list(self.ctx.registry.all_mods)
        except Exception:
            mods = []
        if not mods:
            self.list.addItem("(mods/ 目录是空的)")
            return
        for m in mods:
            tname = packer.TYPE_NAMES.get(_mod_type(m), "?")
            label = "%s  [%s]  %s" % (m.id, tname, getattr(m, "name", ""))
            self.list.addItem(QListWidgetItem(label))

    def _selected_mod_dir(self):
        row = self.list.currentRow()
        if row < 0:
            return None
        mods = list(self.ctx.registry.all_mods)
        if row >= len(mods):
            return None
        m = mods[row]
        d = getattr(m, "dir", "") or getattr(m, "owner_dir", "")
        return d if d and os.path.isdir(d) else None

    def _export(self):
        d = self._selected_mod_dir()
        if not d:
            QMessageBox.information(self, "导出", "先在列表里选中一个模组。")
            return
        mod_id = os.path.basename(os.path.abspath(d))
        default = os.path.join(os.path.expanduser("~"), mod_id + ".zip")
        dest, _sel = QFileDialog.getSaveFileName(
            self, "导出模组", default, "模组包 (*.zip)")
        if not dest:
            return
        try:
            count = packer.export_mod(d, dest)
            QMessageBox.information(self, "导出成功", "%s\n共 %d 个文件 → %s" % (mod_id, count, dest))
        except Exception as e:
            _log.warning("export: %s", e)
            QMessageBox.warning(self, "导出失败", str(e))

    def _import(self):
        src, _sel = QFileDialog.getOpenFileName(
            self, "选择模组包", "", "模组包 (*.zip);;所有文件 (*.*)")
        if not src:
            return
        try:
            new_id, _dest = packer.import_mod_zip(src, paths.MODS_DIR)
        except Exception as e:
            _log.warning("import: %s", e)
            QMessageBox.warning(self, "导入失败", str(e))
            return
        self.ctx.reload()   # 热重载, 新模组立即生效(经 module_manager 线程感知调度)
        self._reload_list()
        QMessageBox.information(self, "导入成功", "模组 %s 已装入 mods/ 并启用。" % new_id)


class Feature:
    id = "feature.packer"
    name = "模组打包"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("模组打包 / 导入", self._open)
        ctx.log("已加载")

    def _open(self):
        win = self.ctx.data.get("win")
        if win is None:
            win = PackerWindow(self.ctx)
            self.ctx.data["win"] = win
        if win.isVisible():
            win.raise_()
        else:
            win.show()
