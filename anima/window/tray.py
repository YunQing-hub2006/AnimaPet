# -*- coding: utf-8 -*-
"""系统托盘(PLAN Phase 5): 角色/皮肤快速切换 + 退出。

托盘在 Qt 主线程创建(main.py 在 app.exec 前实例化), 不参与内核生命周期;
菜单 on aboutToShow 时从注册表重建, 热重载后自动反映新模组。
"""
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from anima.utils import log

_log = log.get("window.tray")


def _make_icon() -> QIcon:
    """用原生 QPainter 画一个圆点图标(不引额外资源)。"""
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    qp = QPainter(pm)
    qp.setRenderHint(QPainter.RenderHint.Antialiasing)
    qp.setBrush(QColor(176, 64, 96))
    qp.setPen(Qt.PenStyle.NoPen)
    qp.drawEllipse(4, 4, 24, 24)
    qp.end()
    return QIcon(pm)


class TrayController(QObject):
    """托盘控制器: 角色/皮肤菜单 + 退出。"""

    def __init__(self, registry, config, bridge, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._config = config
        self._bridge = bridge
        self._tray = QSystemTrayIcon(_make_icon(), self)
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self.refresh)
        self._tray.setContextMenu(self._menu)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()
        self._tray.setToolTip("AnimaPet")
        self.refresh()

    def refresh(self):
        """按当前注册表/配置重建菜单。"""
        menu = self._menu
        menu.clear()
        char_menu = menu.addMenu("角色卡")
        cur_char = str(self._config.get("mods.character", "") or "")
        for cid, c in self._registry.characters.items():
            mark = "● " if cid == cur_char else ""
            act = QAction(mark + c.name, char_menu)
            act.triggered.connect(lambda _f=False, cid=cid: self._switch_char(cid))
            char_menu.addAction(act)
        ui_menu = menu.addMenu("皮肤")
        cur_ui = str(self._config.get("mods.ui", "") or "")
        for uid, u in self._registry.uis.items():
            mark = "● " if uid == cur_ui else ""
            act = QAction(mark + u.name, ui_menu)
            act.triggered.connect(lambda _f=False, uid=uid: self._switch_ui(uid))
            ui_menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("退出", menu)
        quit_act.triggered.connect(lambda _f=False: self._quit())
        menu.addAction(quit_act)

    def _switch_char(self, cid):
        """切换角色(走窗口既有逻辑: 写 config + 刷新 + broadcast)。"""
        win = self._bridge.window if self._bridge is not None else None
        if win is not None:
            win._switch_character(cid)

    def _switch_ui(self, uid):
        """切换皮肤(写 config + 应用 + broadcast)。"""
        win = self._bridge.window if self._bridge is not None else None
        if win is not None:
            win._switch_ui(uid)

    def _quit(self):
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @property
    def tray(self):
        return self._tray