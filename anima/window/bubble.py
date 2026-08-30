# -*- coding: utf-8 -*-
"""头顶气泡: 打字机效果的台词显示器。从 YingPet-v4 core/bubble.py 原样搬运。"""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import QLabel, QWidget

from anima.utils import log, theme

_log = log.get("bubble")


class Bubble(QWidget):
    finished = pyqtSignal()

    def __init__(self, pet):
        super().__init__(None)
        self.pet = pet
        self._full = ""
        self._shown = 0
        self._hold_ms = 0
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.apply_theme({})
        self.label.setFixedWidth(260)
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.hide()

    def apply_theme(self, theme_dict):
        """气泡配色跟随皮肤主题(theme 可只含覆盖键, 自动合并默认)。"""
        t = theme.merge_theme(theme_dict)
        self.label.setStyleSheet(theme.bubble_qss(t))
        self.label.setFont(QFont(t["font_family"], t["font_size"]))

    def is_typing(self):
        """正在打字 = 宠物在"说话"(窗口用它切换说话动画)。"""
        return self._timer.isActive()

    def say(self, text, hold_ms=0):
        self._hide_timer.stop()
        self._timer.stop()
        self._full = str(text)
        self._shown = 0
        if hold_ms <= 0:
            hold_ms = max(2500, len(self._full) * 220)
        self._hold_ms = hold_ms
        self.label.setText("")
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start()

    def _tick(self):
        try:
            self._shown += 1
            self.label.setText(self._full[: self._shown])
            self.label.adjustSize()
            self.resize(self.label.size())
            self._reposition()
            if self._shown >= len(self._full):
                self._timer.stop()
                self._hide_timer.start(self._hold_ms)
                self.finished.emit()
        except Exception as e:
            _log.warning("bubble tick: %s", e)
            self._timer.stop()

    def _reposition(self):
        try:
            self.label.adjustSize()
            self.resize(self.label.size())
            p = self.pet
            x = p.x() + (p.width() - self.width()) // 2
            y = p.y() - self.height() - 8
            screen = QGuiApplication.screenAt(p.geometry().center()) or QGuiApplication.primaryScreen()
            if screen:
                g = screen.availableGeometry()
                x = max(g.left(), min(x, g.right() - self.width()))
                if y < g.top():
                    y = p.y() + p.height() + 8
            self.move(x, y)
        except Exception:
            pass
