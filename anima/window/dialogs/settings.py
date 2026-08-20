# -*- coding: utf-8 -*-
"""设置对话框 (自 YingPet-v4 feature.settings/dialogs.py 的 SettingsDialog 搬运)。

差异: 数据源从 FeatureContext 改为 module_manager 服务(config/registry);
保存走 config 服务; 角色人设写回角色卡 manifest.json 原样保留。
"""
import os

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QPlainTextEdit, QVBoxLayout,
)

from anima.utils import jsonio

WHITE_STYLE = (
    "QDialog { background: #ffffff; color: #111111; }"
    "QLabel { background: transparent; color: #111111; }"
    "QLineEdit, QPlainTextEdit, QComboBox { background: #ffffff; color: #111111;"
    " border: 1px solid #b0b0b0; border-radius: 3px; padding: 4px 6px; }"
    "QDialogButtonBox QPushButton { min-width: 72px; }"
)


class SettingsDialog(QDialog):
    """设置: API 参数 + 当前角色人设(直接写回角色卡 manifest)。"""

    def __init__(self, mm, parent=None):
        super().__init__(parent)
        self.mm = mm
        self.setWindowTitle("设置")
        self.resize(520, 460)
        self.setStyleSheet(WHITE_STYLE)
        self._config = mm.config.data
        layout = QVBoxLayout(self)
        form = QFormLayout()
        api = self._config.setdefault("api", {})
        self.ed_key = QLineEdit(api.get("api_key", ""))
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_base = QLineEdit(api.get("base_url", ""))
        self.ed_model = QComboBox()
        self.ed_model.setEditable(True)
        self.ed_model.addItems(["deepseek-v4-flash", "deepseek-v4-pro"])
        self.ed_model.setCurrentText(api.get("model", "deepseek-v4-flash"))
        self.ed_temp = QLineEdit(str(api.get("temperature", 0.8)))
        self.ed_temp.setPlaceholderText("0.0 ~ 2.0, 越高越放飞")
        self.ed_effort = QComboBox()
        self.ed_effort.addItems(["默认", "低 (low)", "中 (medium)", "高 (high)"])
        effort_map = {"": 0, "low": 1, "medium": 2, "high": 3}
        self.ed_effort.setCurrentIndex(effort_map.get(str(api.get("reasoning_effort", "")), 0))
        form.addRow("API Key", self.ed_key)
        form.addRow("Base URL", self.ed_base)
        form.addRow("模型", self.ed_model)
        form.addRow("温度", self.ed_temp)
        form.addRow("思考强度", self.ed_effort)
        layout.addLayout(form)

        char_label = QLabel("—— 当前角色人设 (保存后写回角色卡 manifest.json) ——")
        char_label.setStyleSheet("color: #a08cb0;")
        layout.addWidget(char_label)
        self.char = self._current_char()
        self.ed_prompt = QPlainTextEdit()
        self.ed_prompt.setPlainText(self.char.system_prompt if self.char else "")
        self.ed_prompt.setPlaceholderText("没有启用角色卡时, 这里为空")
        layout.addWidget(self.ed_prompt, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _current_char(self):
        cid = str(self.mm.config.get("mods.character", ""))
        c = self.mm.registry.character(cid)
        if c is None and self.mm.registry.characters:
            c = next(iter(self.mm.registry.characters.values()))
        return c

    def _save(self):
        api = self._config["api"]
        api["api_key"] = self.ed_key.text().strip()
        api["base_url"] = self.ed_base.text().strip() or "https://api.deepseek.com"
        api["model"] = self.ed_model.currentText().strip() or "deepseek-v4-flash"
        try:
            t = float(self.ed_temp.text().strip())
            api["temperature"] = min(2.0, max(0.0, t))
        except (TypeError, ValueError):
            api["temperature"] = 0.8
        api["reasoning_effort"] = ["", "low", "medium", "high"][self.ed_effort.currentIndex()]
        self.mm.config.save()
        if self.char is not None:
            self.char.system_prompt = self.ed_prompt.toPlainText().strip() or self.char.system_prompt
            self.char.raw["system_prompt"] = self.char.system_prompt
            jsonio.save(os.path.join(self.char.dir, "manifest.json"), self.char.raw)
        self.accept()
