# -*- coding: utf-8 -*-
"""皮肤工坊: 用取色器调配色, 实时预览, 保存即生成 ui.* 皮肤模组。

面向新手的自定义皮肤入口 —— 不用懂 QSS/JSON, 点颜色块改配色, 起个名字
保存, 皮肤列表立刻多一套(可选立即应用)。字体/字号不在这里改, 保证布局
稳定; 高级用户可直接改 mods/ui.*/manifest.json 里的 theme 字典。
"""
import os
import re

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)

from anima.utils import jsonio, log, paths, theme
from anima.window.dialogs.common import apply_dialog_style

_log = log.get("feature.skinmaker")

#: 暴露给新手的配色项: (分组, 中文说明, theme 键)
_COLOR_FIELDS = (
    ("窗口与聊天区", [
        ("窗口底色", "bg_window"),
        ("聊天区底色", "bg_browser"),
        ("输入框底色", "bg_panel"),
        ("界面文字", "fg_browser"),
        ("输入框文字", "fg_panel"),
        ("次要文字/提示", "status_fg"),
    ]),
    ("主色与按钮", [
        ("主色(边框/选中)", "accent"),
        ("主色悬停", "accent_hover"),
        ("按钮底色", "btn_bg"),
        ("按钮文字", "btn_fg"),
    ]),
    ("气泡与菜单", [
        ("我说的话·气泡", "user_bubble_bg"),
        ("我说的话·文字", "user_bubble_fg"),
        ("宠物气泡", "pet_bubble_bg"),
        ("宠物气泡文字", "pet_bubble_fg"),
        ("头顶气泡·底色", "bubble_bg"),
        ("头顶气泡·文字", "bubble_fg"),
        ("菜单底色", "menu_bg"),
        ("菜单文字", "menu_fg"),
        ("菜单选中", "menu_hover"),
    ]),
)


class _SkinPreview(QWidget):
    """迷你聊天预览: 跟随当前配色即时重绘。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.browser = QTextBrowser()
        self.browser.setFixedHeight(150)
        v.addWidget(self.browser)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("预览: 说点什么…")
        row.addWidget(self.input, 1)
        self.btn_send = QPushButton("发送")
        self.btn_send.setObjectName("btn_send")
        row.addWidget(self.btn_send)
        v.addLayout(row)

    def apply(self, t):
        self.setStyleSheet(theme.panel_qss(t))
        self.browser.clear()
        self.browser.append(
            '<div align="right" style="margin:4px 0;">'
            '<span style="background:%s; color:%s; border-radius:8px; padding:3px 7px;">'
            "今天穿什么好看?</span></div>"
            '<div align="left" style="margin:4px 0;">'
            '<span style="color:%s;">影: </span>'
            '<span style="background:%s; color:%s; border-radius:8px; padding:3px 7px;">'
            "就穿现在这套, 挺好的。</span></div>"
            % (t["user_bubble_bg"], t["user_bubble_fg"], t["accent"],
               t["pet_bubble_bg"], t["pet_bubble_fg"]))


class SkinMakerDialog(QDialog):
    """皮肤工坊: 取色 → 预览 → 保存为 ui.* 模组(可选立即应用)。

    host 需要提供: ``registry``(现有皮肤/冲突检查)、``config``(get/set/save
    接口, 与 module_manager.config / charcard 的 _ConfigFacade 一致);
    可选提供 ``rescan()``(保存后热重载)。
    """

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.created_id = ""
        self.setWindowTitle("皮肤工坊")
        self.resize(560, 640)
        apply_dialog_style(self)

        # 起点配色: 当前皮肤(没有就用默认主题); rgba() 取色器读不了, 换等价 hex
        self._colors = dict(theme.merge_theme(self._current_skin_theme()))
        self._colors.setdefault("bubble_bg", "#1e1428")

        root = QVBoxLayout(self)
        root.addWidget(self._build_base_row())
        root.addWidget(self._build_color_groups(), 1)
        root.addWidget(self._build_preview())
        root.addWidget(self._build_save_row())

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------

    def _current_skin_theme(self):
        try:
            uid = str(self.host.config.get("mods.ui", "") or "")
            skin = self.host.registry.ui(uid) if uid else None
            return skin.theme if skin else {}
        except Exception:
            return {}

    def _build_base_row(self):
        box = QGroupBox("起点")
        h = QHBoxLayout(box)
        h.addWidget(QLabel("从这套开始改:"))
        self.cmb_base = QComboBox()
        self.cmb_base.addItem("默认主题", "")
        for uid, u in sorted(self.host.registry.uis.items()):
            self.cmb_base.addItem("%s (%s)" % (u.name, uid), uid)
        h.addWidget(self.cmb_base, 1)
        btn_load = QPushButton("载入")
        btn_load.clicked.connect(self._load_base)
        h.addWidget(btn_load)
        return box

    def _build_color_groups(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self._swatches = {}
        for group, fields in _COLOR_FIELDS:
            gb = QGroupBox(group)
            grid = QFormLayout(gb)
            grid.setSpacing(4)
            for label, key in fields:
                grid.addRow(QLabel(label), self._color_button(key, label))
            v.addWidget(gb)
        return w

    def _build_preview(self):
        gb = QGroupBox("实时预览")
        v = QVBoxLayout(gb)
        self.preview = _SkinPreview()
        v.addWidget(self.preview)
        self._refresh_preview()
        return gb

    def _build_save_row(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.ed_id = QLineEdit()
        self.ed_id.setPlaceholderText("如 my_skin 或 ui.my_skin(小写字母/数字/_.-)")
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("皮肤显示名, 如 我的夜色")
        form.addRow("皮肤 id", self.ed_id)
        form.addRow("名称", self.ed_name)
        v.addLayout(form)
        row = QHBoxLayout()
        self.chk_apply = QCheckBox("保存后立即换上")
        self.chk_apply.setChecked(True)
        row.addWidget(self.chk_apply)
        row.addStretch(1)
        v.addLayout(row)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        return w

    # ------------------------------------------------------------------
    # 取色 / 预览
    # ------------------------------------------------------------------

    def _color_button(self, key, label):
        btn = QPushButton()
        btn.setFixedSize(72, 22)
        btn.setToolTip("%s — 点这里选颜色" % label)

        def pick(_checked=False, key=key, btn=btn):
            col = QColorDialog.getColor(QColor(self._colors.get(key, "#000000")),
                                        self, "选择%s" % label)
            if col.isValid():
                self._colors[key] = col.name()
                self._refresh_swatch(btn, key)
                self._refresh_preview()

        btn.clicked.connect(pick)
        self._swatches[key] = btn
        self._refresh_swatch(btn, key)
        return btn

    def _refresh_swatch(self, btn, key):
        c = self._colors.get(key, "")
        text = c if str(c).startswith("#") else "#1e1428"
        btn.setStyleSheet(
            "QPushButton { background: %s; border: 1px solid #888;"
            " border-radius: 4px; min-width: 0; padding: 0; }" % text)
        btn.setText("")

    def _refresh_preview(self):
        self.preview.apply(theme.merge_theme(self._colors))

    def _load_base(self):
        uid = str(self.cmb_base.currentData() or "")
        skin = self.host.registry.ui(uid) if uid else None
        merged = theme.merge_theme(skin.theme if skin else {})
        self._colors = dict(merged)
        self._colors.setdefault("bubble_bg", "#1e1428")
        for key, btn in self._swatches.items():
            self._refresh_swatch(btn, key)
        self._refresh_preview()

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _save(self):
        base = self.ed_id.text().strip().lower()
        if base.startswith("ui."):
            base = base[len("ui."):]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", base or ""):
            QMessageBox.warning(self, "id 不合法",
                                "只允许小写字母/数字/_.-，且不能以符号开头。")
            return
        uid = "ui." + base
        if uid in self.host.registry.uis or os.path.isdir(os.path.join(paths.MODS_DIR, uid)):
            QMessageBox.warning(self, "id 冲突", "皮肤已存在: " + uid)
            return
        name = self.ed_name.text().strip() or base
        d = os.path.join(paths.MODS_DIR, uid)
        try:
            os.makedirs(d, exist_ok=True)
            jsonio.save(os.path.join(d, "manifest.json"), {
                "id": uid, "type": "ui", "version": "1.0.0",
                "name": name, "description": "皮肤工坊生成的自定义皮肤",
                "theme": dict(self._colors),
            })
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return
        if self.chk_apply.isChecked():
            self.host.config.set("mods.ui", uid)
            self.host.config.save()
        rescan = getattr(self.host, "rescan", None)
        if rescan is not None:
            try:
                rescan()
            except Exception as e:
                _log.warning("skinmaker rescan: %s", e)
        self.created_id = uid
        self.accept()
