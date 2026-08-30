# -*- coding: utf-8 -*-
"""聊天面板 UI (自 YingPet-v4 feature.chat/chat_panel.py 平移)。

职责边界: 本类只管"显示与输入" —— 消息渲染、主题、新手引导;
收发/历史存取由 plugins/chat.py 的 ChatFeature 控制(信号槽连接)。

新手友好设计:
- 工具栏按使用频率分组: 常用(新对话/历史/角色)在左, 低频(备份/清空)收进菜单;
- 每个按钮都有"做什么"式 tooltip;
- 首次打开且无历史时显示欢迎引导(welcome);
- 历史回放走 add_messages() 批量渲染, 一次文档重排, 几百条消息也不卡。
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
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
        self.resize(420, 560)
        self.setMinimumSize(320, 360)
        self._theme = dict(theme.DEFAULT_THEME)
        self._base_status = ""      # 状态文本(不含好感度), 由 set_status 维护
        self._affinity = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        self._build_toolbar(layout)
        self._build_search_row(layout)
        self._build_browser(layout)
        self._build_input_row(layout)
        self.apply_theme({})

    # ------------------------------------------------------------------
    # 界面搭建
    # ------------------------------------------------------------------

    def _build_toolbar(self, layout):
        top = QHBoxLayout()
        self.btn_new = self._tool_button("新对话", "和宠物开启一段新对话, 旧记录仍可在「历史」里找到",
                                         self.new_conv_requested.emit)
        top.addWidget(self.btn_new)
        self.btn_history = self._tool_button("历史", "查看历史对话列表; 看完点「返回」回到当前对话",
                                             self.history_requested.emit)
        top.addWidget(self.btn_history)
        self.btn_back = self._tool_button("返回", "回到当前对话")
        self.btn_back.clicked.connect(self._do_back)
        self.btn_back.hide()
        top.addWidget(self.btn_back)
        self.cb_card = QComboBox()
        self.cb_card.setToolTip("切换聊天对象(当前角色卡)")
        self.cb_card.setMinimumWidth(90)
        self.cb_card.currentIndexChanged.connect(self._on_card_changed)
        top.addWidget(self.cb_card)
        top.addStretch(1)

        self.btn_backup = self._tool_button("备份 ▾", "把聊天记录导出为文件, 或从文件恢复")
        menu = QMenu(self.btn_backup)
        menu.addAction("导出为 TXT…", self.export_history_requested.emit)
        menu.addAction("导出为 JSON…", self.export_json_requested.emit)
        menu.addAction("从 JSON 恢复…", self.import_json_requested.emit)
        self.btn_backup.setMenu(menu)
        top.addWidget(self.btn_backup)
        self.btn_clear = self._tool_button("清空", "删除全部聊天记录(不可恢复)",
                                           self.clear_history_requested.emit)
        top.addWidget(self.btn_clear)
        layout.addLayout(top)

    def _build_search_row(self, layout):
        row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("在聊天记录里找一句话…")
        self.search_box.setToolTip("输入关键词后回车, 只显示匹配的历史消息")
        self.search_box.returnPressed.connect(self._do_search)
        row.addWidget(self.search_box, 1)
        self.btn_search = self._tool_button("搜索", "在全部聊天记录里搜索关键词",
                                            self._do_search)
        row.addWidget(self.btn_search)
        layout.addLayout(row)

    def _build_browser(self, layout):
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(
            lambda url: self.history_conv_requested.emit(url.toString()))
        layout.addWidget(self.browser, 1)
        self.status = QLabel("")
        self.status.setObjectName("lbl_status")
        layout.addWidget(self.status)

    def _build_input_row(self, layout):
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("说点什么… 回车发送")
        self.input.setToolTip("在这里打字, 按回车或点「发送」")
        self.input.returnPressed.connect(self._send)
        row.addWidget(self.input, 1)
        self.btn_send = QPushButton("发送")
        self.btn_send.setObjectName("btn_send")
        self.btn_send.setToolTip("发送消息给宠物 (回车也可以)")
        self.btn_send.clicked.connect(self._send)
        row.addWidget(self.btn_send)
        layout.addLayout(row)

    @staticmethod
    def _tool_button(text, tip, callback=None):
        b = QPushButton(text)
        b.setToolTip(tip)
        if callback is not None:
            b.clicked.connect(callback)
        return b

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def apply_theme(self, theme_dict):
        """应用皮肤主题; 皮肤模组热重载后由插件调用。"""
        t = self._theme = theme.merge_theme(theme_dict)
        font = QFont(t["font_family"], t["font_size"])
        self.setFont(font)
        self.browser.setFont(font)
        self.input.setFont(font)
        self.setStyleSheet(theme.append_qss(theme.panel_qss(t), t.get("qss")))

    # ------------------------------------------------------------------
    # 输入 / 搜索
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 展示(单条)
    # ------------------------------------------------------------------

    @staticmethod
    def esc(text):
        return (str(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))

    def _bubble_html(self, text, bg, fg):
        return theme.chat_bubble_html(bg, fg, self.esc(text))

    def add_user(self, text):
        t = self._theme
        self.browser.append(
            '<div align="right" style="margin:9px 0;">'
            + self._bubble_html(text, t["user_bubble_bg"], t["user_bubble_fg"])
            + "</div>")
        self._scroll_bottom()

    def _name_html(self, name):
        """宠物名字: 主色加粗, 与气泡拉开主次。"""
        return ('<span style="color:%s; font-weight:bold;">%s&nbsp;</span>'
                % (self._theme["accent"], self.esc(name)))

    def add_pet(self, text, name="影"):
        t = self._theme
        self.browser.append(
            '<div align="left" style="margin:9px 0;">'
            + self._name_html(name)
            + self._bubble_html(text, t["pet_bubble_bg"], t["pet_bubble_fg"])
            + "</div>")
        self._scroll_bottom()

    def add_system(self, text):
        self.browser.append(
            '<div align="center" style="color:%s; font-size:11px; margin:4px 0;">'
            % self._theme["status_fg"] + self.esc(text) + "</div>")
        self._scroll_bottom()

    def add_messages(self, messages, name="影"):
        """批量渲染一组历史消息: 拼成一段 HTML 一次 append, 只触发一次文档重排。"""
        if not messages:
            return
        t = self._theme
        parts = []
        for m in messages:
            prefix = "[%s] " % m.get("ts", "") if m.get("ts") else ""
            if m.get("role") == "user":
                parts.append('<div align="right" style="margin:9px 0;">'
                             + self._bubble_html(prefix + m.get("content", ""),
                                                 t["user_bubble_bg"], t["user_bubble_fg"])
                             + "</div>")
            else:
                parts.append('<div align="left" style="margin:9px 0;">'
                             + self._name_html(name)
                             + self._bubble_html(prefix + m.get("content", ""),
                                                 t["pet_bubble_bg"], t["pet_bubble_fg"])
                             + "</div>")
        self.browser.append("".join(parts))
        self._scroll_bottom()

    def add_welcome(self, pet_name):
        """空历史时的新手引导: 三句话讲清怎么用。"""
        t = self._theme
        self.browser.append(
            '<div style="margin:18px 10px; color:%s; line-height:1.7;">'
            '<div style="font-size:14px; font-weight:bold; color:%s; margin-bottom:8px;">'
            '%s 在等你说话啦</div>'
            '<div>· 在下方输入框打字，回车发送</div>'
            '<div>· 点「历史」翻看以前的对话</div>'
            '<div>· 回复失败时，去宠物右键菜单 →「设置 (API / 人设)」填写 API Key</div>'
            "</div>" % (t["status_fg"], t["accent"], self.esc(pet_name)))
        self._scroll_bottom()

    def add_history_list(self, groups, current_conv):
        """历史对话列表(groups: {conv_id: [msg]}) — 标记在面板内, chat.py 只传数据。"""
        t = self._theme
        self.add_system("—— 历史对话列表（点链接查看；点“返回”回到当前对话）——")
        parts = []
        for conv in sorted(groups, reverse=True):
            msgs = groups[conv]
            ts = str(msgs[0].get("ts", "") or "")
            first = next((str(m.get("content", "")) for m in msgs if m.get("role") == "user"),
                         str(msgs[0].get("content", "")))
            snippet = self.esc(first)
            if len(snippet) > 30:
                snippet = snippet[:30] + "…"
            cur = "（当前）" if conv == current_conv else ""
            parts.append(
                '<div style="margin:5px 0;">'
                '<a href="conv:%d" style="color:%s; font-weight:bold; text-decoration:none;">'
                '[对话 %d]</a>'
                ' <span style="color:%s;">%s ｜ %d 条 %s</span><br>'
                '<span style="color:%s; font-size:11px;">%s</span></div>'
                % (conv, t["accent"], conv, t["status_fg"], ts, len(msgs), cur,
                   t["fg_browser"], snippet))
        self.browser.append("".join(parts))
        self._scroll_bottom()

    def clear(self):
        self.browser.clear()

    def set_searching(self, on):
        self.btn_back.setVisible(on)

    # ------------------------------------------------------------------
    # 状态栏: 基础状态 + 好感度 分开维护, 不再靠字符串切割拼装
    # ------------------------------------------------------------------

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

    def set_status(self, text):
        self._base_status = str(text or "")
        self._refresh_status()

    def _refresh_status(self):
        parts = [s for s in (self._base_status.strip(),
                             "好感度: %d" % self._affinity if self._affinity else "") if s]
        self.status.setText(" ｜ ".join(parts))

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
