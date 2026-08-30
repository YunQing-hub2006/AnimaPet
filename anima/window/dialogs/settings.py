# -*- coding: utf-8 -*-
"""设置对话框 (自 YingPet-v4 feature.settings/dialogs.py 的 SettingsDialog 平移)。

新手向导式布局:
    第一步「对话模型」— API Key / 接口地址 / 模型 / 性格温度 / 思考强度,
        每项配一句"这是什么"悬停说明, 没配 Key 也能看懂该填哪里;
    第二步「角色人设」— 当前角色的 system_prompt, 保存后写回角色卡。

保存走 config 服务; 角色人设写回角色卡 manifest.json, 逻辑与旧版一致。
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QSlider, QVBoxLayout, QWidget,
)

from anima.utils import jsonio
from anima.window.dialogs.common import apply_dialog_style


class SettingsDialog(QDialog):
    """设置: API 参数 + 当前角色人设(直接写回角色卡 manifest)。"""

    # (存储值, 显示名) — 与 api.reasoning_effort 的取值一一对应
    _EFFORTS = [("", "默认(跟随模型)"), ("low", "低 · 更快更省"),
                ("medium", "中 · 均衡"), ("high", "高 · 更聪明更慢")]

    def __init__(self, mm, parent=None):
        super().__init__(parent)
        self.mm = mm
        self.setWindowTitle("设置")
        self.resize(540, 520)
        apply_dialog_style(self)
        self._config = mm.config.data

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_api_box())
        layout.addWidget(self._build_char_box(), 1)
        layout.addWidget(self._build_buttons())

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------

    def _build_api_box(self):
        box = QGroupBox("① 对话模型(不填 Key 桌宠照样跑, 聊天才需要)")
        form = QFormLayout(box)
        form.setSpacing(8)
        api = self._config.setdefault("api", {})

        self.ed_key = QLineEdit(api.get("api_key", ""))
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_key.setPlaceholderText("sk-…(在模型服务商的开放平台创建)")
        form.addRow(self._field("API Key", "模型的钥匙, 只保存在你自己的电脑上"), self.ed_key)

        self.ed_base = QLineEdit(api.get("base_url", ""))
        self.ed_base.setPlaceholderText("默认 https://api.deepseek.com")
        form.addRow(self._field("接口地址", "服务商提供的 API 网址, 用 DeepSeek 就不用改"), self.ed_base)

        self.ed_model = QComboBox()
        self.ed_model.setEditable(True)
        self.ed_model.addItems(["deepseek-v4-flash", "deepseek-v4-pro"])
        self.ed_model.setCurrentText(api.get("model", "deepseek-v4-flash"))
        form.addRow(self._field("模型", "flash 便宜快速, pro 更聪明"), self.ed_model)

        self.sld_temp = QSlider(Qt.Orientation.Horizontal)
        self.sld_temp.setRange(0, 20)          # 0.0 ~ 2.0, 步长 0.1
        self.sld_temp.setValue(self._temp_to_slider(api.get("temperature", 0.8)))
        self.lbl_temp = QLabel("%.1f" % (self.sld_temp.value() / 10.0))
        self.lbl_temp.setMinimumWidth(36)
        self.sld_temp.valueChanged.connect(
            lambda v: self.lbl_temp.setText("%.1f" % (v / 10.0)))
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.sld_temp, 1)
        temp_row.addWidget(self.lbl_temp)
        form.addRow(self._field("性格温度", "越低越稳重, 越高越放飞(0~2)"),
                    self._wrap(temp_row))

        self.ed_effort = QComboBox()
        for _val, name in self._EFFORTS:
            self.ed_effort.addItem(name)
        effort_map = {v: i for i, (v, _n) in enumerate(self._EFFORTS)}
        self.ed_effort.setCurrentIndex(effort_map.get(str(api.get("reasoning_effort", "")), 0))
        form.addRow(self._field("思考强度", "回答前『想一想』的程度; 仅部分模型支持"),
                    self.ed_effort)
        return box

    def _build_char_box(self):
        box = QGroupBox("② 当前角色人设(保存后写回角色卡, 即改即生效)")
        vbox = QVBoxLayout(box)
        self.char = self._current_char()
        self.ed_prompt = QPlainTextEdit()
        self.ed_prompt.setPlainText(self.char.system_prompt if self.char else "")
        self.ed_prompt.setPlaceholderText("没有启用角色卡时, 这里为空")
        vbox.addWidget(self.ed_prompt, 1)
        return box

    def _build_buttons(self):
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        return btns

    # ------------------------------------------------------------------
    # 小工具
    # ------------------------------------------------------------------

    @staticmethod
    def _field(name, tip):
        """表单左列: 字段名 + 悬停解释(新手不懂术语时鼠标放上去看)。"""
        lbl = QLabel(name)
        lbl.setToolTip(tip)
        return lbl

    @staticmethod
    def _wrap(layout):
        """把一行布局包成 QWidget(QFormLayout 只吃控件)。"""
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _temp_to_slider(value):
        try:
            return round(min(2.0, max(0.0, float(value))) * 10)
        except (TypeError, ValueError):
            return 8   # 默认 0.8

    def _current_char(self):
        cid = str(self.mm.config.get("mods.character", ""))
        c = self.mm.registry.character(cid)
        if c is None and self.mm.registry.characters:
            c = next(iter(self.mm.registry.characters.values()))
        return c

    # ------------------------------------------------------------------
    # 保存(与旧版逻辑一致: config 服务 + 角色卡 manifest 写回)
    # ------------------------------------------------------------------

    def _save(self):
        api = self._config["api"]
        api["api_key"] = self.ed_key.text().strip()
        api["base_url"] = self.ed_base.text().strip() or "https://api.deepseek.com"
        api["model"] = self.ed_model.currentText().strip() or "deepseek-v4-flash"
        api["temperature"] = self.sld_temp.value() / 10.0
        api["reasoning_effort"] = self._EFFORTS[self.ed_effort.currentIndex()][0]
        self.mm.config.save()
        if self.char is not None:
            self.char.system_prompt = self.ed_prompt.toPlainText().strip() or self.char.system_prompt
            self.char.raw["system_prompt"] = self.char.system_prompt
            jsonio.save(os.path.join(self.char.dir, "manifest.json"), self.char.raw)
        self.accept()
