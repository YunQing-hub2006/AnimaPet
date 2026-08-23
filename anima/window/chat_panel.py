# -*- coding: utf-8 -*-
"""聊天面板 UI (自 YingPet-v4 feature.chat/chat_panel.py 搬运)。

差异: 数据源从 FeatureContext 改为 chat 插件服务(信号槽不变);
新增导出/导入 JSON 按钮(Phase 4 历史 JSON 导入导出)。
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
)

from anima.utils import log, theme

_log = log.get("chat.panel")


class ChatPanel(QWidget):
    send_requested = pyqtSignal(str)
    new_conv_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    search_cleared = pyqtSignal()
    clear_history_requested = pyqtSignal()
    export_history_requested = pyqtSignal()
    export_json_requested = pyqtSignal()
    import_json_requested = pyqtSignal()
    card_switch_requested = pyqtSignal(str)
    history_requested = pyqtSignal()
    history_conv_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowTitle("聊天")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(380, 460)
        layout = QVBoxLayout(self)
        self._theme = dict(theme.DEFAULT_THEME)

        top = QHBoxLayout()
        self.btn_new = QPushButton("新对话")
        self.btn_new.setToolTip("开启新对话, 旧记录仍保留可搜索")
        self.btn_new.clicked.connect(self.new_conv_requested.emit)
        top.addWidget(self.btn_new)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setToolTip("清空全部聊天记录(不可恢复)")
        self.btn_clear.clicked.connect(self.clear_history_requested.emit)
        top.addWidget(self.btn_clear)
        self.btn_export = QPushButton("导出")
        self.btn_export.setToolTip("导出聊天记录为 txt 文件")
        self.btn_export.clicked.connect(self.export_history_requested.emit)
        top.addWidget(self.btn_export)
        self.btn_history = QPushButton("历史")
        self.btn_history.setToolTip("查看历史对话列表; 返回键回到当前对话")
        self.btn_history.clicked.connect(self.history_requested.emit)
        top.addWidget(self.btn_history)
        self.cb_card = QComboBox()
        self.cb_card.setMinimumWidth(90)
        self.cb_card.currentIndexChanged.connect(self._on_card_changed)
        top.addWidget(self.cb_card)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索历史聊天…")
        self.search_box.returnPressed.connect(self._do_search)
        top.addWidget(self.search_box, 1)
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self._do_search)
        top.addWidget(self.btn_search)
        self.btn_back = QPushButton("返回")
        self.btn_back.clicked.connect(self._do_back)
        self.btn_back.hide()
        top.addWidget(self.btn_back)
        layout.addLayout(top)

        row2 = QHBoxLayout()
        self.btn_export_json = QPushButton("导出 JSON")
        self.btn_export_json.setToolTip("导出当前角色聊天记录为 JSON")
        self.btn_export_json.clicked.connect(self.export_json_requested.emit)
        row2.addWidget(self.btn_export_json)
        self.btn_import_json = QPushButton("导入 JSON")
        self.btn_import_json.setToolTip("从 JSON 导入当前角色聊天记录(覆盖)")
        self.btn_import_json.clicked.connect(self.import_json_requested.emit)
        row2.addWidget(self.btn_import_json)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(
            lambda url: self.history_conv_requested.emit(url.toString()))
        layout.addWidget(self.browser, 1)

        self.status = QLabel("")
        layout.addWidget(self.status)
        self._affinity = 0

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("说点什么… 回车发送")
        self.input.returnPressed.connect(self._send)
        self.btn_send = QPushButton("发送")
        self.btn_send.clicked.connect(self._send)
        row.addWidget(self.input, 1)
        row.addWidget(self.btn_send)
        layout.addLayout(row)
        self.apply_theme({})

    # ---- 主题 ----
    def apply_theme(self, theme_dict):
        """应用皮肤主题; 皮肤模组热重载后由插件调用。"""
        from PyQt6.QtGui import QFont
        t = self._theme = theme.merge_theme(theme_dict)
        font = QFont(t["font_family"], t["font_size"])
        btn_style = (
            "QPushButton {{ background: {btn_bg}; color: {btn_fg};"
            " border: 1px solid {accent}; border-radius: 6px; padding: 4px 10px; }}"
            "QPushButton:hover {{ background: {accent}; }}"
        ).format(**t)
        for b in (self.btn_new, self.btn_clear, self.btn_export,
                  self.btn_export_json, self.btn_import_json,
                  self.btn_search, self.btn_back):
            b.setStyleSheet(btn_style)
        self.cb_card.setStyleSheet(
            "QComboBox {{ background: {bg_panel}; color: {fg_panel};"
            " border: 1px solid {accent}; border-radius: 6px; padding: 4px 6px; }}"
            "QComboBox QAbstractItemView {{ background: {bg_panel}; color: {fg_panel}; }}"
            .format(**t))
        panel_style = (
            "QLineEdit {{ background: {bg_panel}; color: {fg_panel};"
            " border: 1px solid {accent}; border-radius: 6px; padding: 4px 8px; }}"
        ).format(**t)
        self.search_box.setStyleSheet(panel_style)
        self.browser.setFont(font)
        self.browser.setStyleSheet(
            "QTextBrowser {{ background: {bg_browser}; color: {fg_browser};"
            " border: 1px solid {accent}; border-radius: 8px; padding: 6px; }}"
            .format(**t))
        self.status.setStyleSheet("color: %s; font-size: 11px;" % t["status_fg"])
        self.input.setFont(font)
        self.input.setStyleSheet(
            "QLineEdit {{ background: {bg_panel}; color: {fg_panel};"
            " border: 1px solid {accent}; border-radius: 8px; padding: 6px; }}"
            .format(**t))
        self.btn_send.setStyleSheet(
            "QPushButton {{ background: {accent}; color: white; border-radius: 8px;"
            " padding: 6px 16px; }}QPushButton:hover {{ background: {accent_hover}; }}"
            .format(**t))
        extra = t.get("qss", "")
        if extra:
            self.setStyleSheet(extra)

    # ---- 信号 ----
    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.send_requested.emit(text)

    def _do_search(self):
        kw = self.search_box.text().strip()
        if kw:
            self.btn_back.show()
            self.search_requested.emit(kw)

    def _do_back(self):
        self.search_box.clear()
        self.btn_back.hide()
        self.search_cleared.emit()

    def _on_card_changed(self, idx):
        if idx < 0:
            return
        cid = self.cb_card.itemData(idx)
        if cid:
            self.card_switch_requested.emit(cid)

    # ---- 展示 ----
    def set_cards(self, cards, current_id):
        """cards: [(id, name)]"""
        self.cb_card.blockSignals(True)
        self.cb_card.clear()
        for cid, name in cards:
            self.cb_card.addItem(name, cid)
        idx = self.cb_card.findData(current_id)
        self.cb_card.setCurrentIndex(max(0, idx))
        self.cb_card.blockSignals(False)

    def set_affinity(self, value):
        self._affinity = int(value or 0)
        self._refresh_status()

    def _refresh_status(self):
        base = self.status.text().split(" | ")[0] if " | " in self.status.text() else self.status.text()
        self.status.setText((base + " | 好感度: " + str(self._affinity)) if base.strip()
                            else ("好感度: " + str(self._affinity)))

    def clear(self):
        self.browser.clear()

    def set_searching(self, on):
        self.btn_back.setVisible(on)

    @staticmethod
    def esc(text):
        return (str(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))

    def add_user(self, text):
        t = self._theme
        self.browser.append(
            '<div align="right" style="margin:6px 0;">'
            '<span style="background:%s; color:%s; border-radius:8px; padding:4px 8px;">'
            % (t["user_bubble_bg"], t["user_bubble_fg"])
            + self.esc(text) + "</span></div>")
        self._scroll_bottom()

    def add_pet(self, text, name="影"):
        t = self._theme
        self.browser.append(
            '<div align="left" style="margin:6px 0;">'
            '<span style="color:%s;">' % t["accent"] + self.esc(name) + ': </span>'
            '<span style="background:%s; color:%s; border-radius:8px; padding:4px 8px;">'
            % (t["pet_bubble_bg"], t["pet_bubble_fg"])
            + self.esc(text) + "</span></div>")
        self._scroll_bottom()

    def add_system(self, text):
        self.browser.append(
            '<div align="center" style="color:%s; font-size:11px; margin:4px 0;">'
            % self._theme["status_fg"]
            + self.esc(text) + "</div>")
        self._scroll_bottom()

    def set_status(self, text):
        self.status.setText(text)
        self._refresh_status()

    def closeEvent(self, e):
        """点聊天窗口的 × 只隐藏, 不关闭: 桌面宠物本体必须保持运行。"""
        e.ignore()
        self.hide()

    def _scroll_bottom(self):
        try:
            sb = self.browser.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass
