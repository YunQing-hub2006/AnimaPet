# -*- coding: utf-8 -*-
"""待办清单: 白底黑字小窗, 增删勾选, 全程持久化。自 YingPet-v4 平移(无改动)。

- 条目存 state.json 的 todo.items: [{"text": str, "done": bool}]
- 每天首次加载播报未完成数(记录 todo.last_day 防重复)
- 窗口实例存 ctx.data["win"], 跨热重载不重复开窗
"""
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

STYLE = (
    "QWidget { background: #ffffff; color: #111111; font-family: 'Microsoft YaHei'; }"
    "QLineEdit { background: #ffffff; border: 1px solid #b0b0b0;"
    " border-radius: 3px; padding: 5px 8px; }"
    "QListWidget { background: #ffffff; border: 1px solid #c0c0c0; }"
    "QListWidget::item { padding: 4px; }"
    "QListWidget::item:selected { background: #d6e4ff; color: #000000; }"
    "QPushButton { background: #f2f2f2; border: 1px solid #b0b0b0;"
    " border-radius: 3px; padding: 5px 14px; }"
    "QPushButton:hover { background: #e2e2e2; }"
)


class TodoWindow(QWidget):
    def __init__(self, ctx):
        super().__init__(None)
        self.ctx = ctx
        self.setWindowTitle("待办清单")
        self.setStyleSheet(STYLE)
        self.resize(340, 420)
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("新待办, 回车添加")
        self.input.returnPressed.connect(self._add)
        row.addWidget(self.input, 1)
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._add)
        row.addWidget(btn_add)
        layout.addLayout(row)

        self.list = QListWidget()
        self.list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list, 1)

        row2 = QHBoxLayout()
        btn_done = QPushButton("完成勾选")
        btn_done.clicked.connect(self._toggle_selected)
        row2.addWidget(btn_done)
        btn_del = QPushButton("删除选中")
        btn_del.clicked.connect(self._del_selected)
        row2.addWidget(btn_del)
        btn_clear = QPushButton("清空已完成")
        btn_clear.clicked.connect(self._clear_done)
        row2.addWidget(btn_clear)
        layout.addLayout(row2)

        self._loading = True
        self._reload()
        self._loading = False

    # ---- 数据 ----
    def _items(self):
        items = self.ctx.get_state("todo.items") or []
        return [it for it in items if isinstance(it, dict) and str(it.get("text", "")).strip()]

    def _save(self, items):
        self.ctx.set_state("todo.items", items)

    def _reload(self):
        self.list.blockSignals(True)
        self.list.clear()
        for it in self._items():
            item = QListWidgetItem(("[已完成] " if it.get("done") else "[待办] ") + str(it["text"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if it.get("done") else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)

    # ---- 动作 ----
    def _add(self):
        text = self.input.text().strip()
        if not text:
            return
        items = self._items()
        items.append({"text": text, "done": False})
        self._save(items)
        self.input.clear()
        self._reload()

    def _selected_rows(self):
        return sorted({i.row() for i in self.list.selectedIndexes()}, reverse=True)

    def _del_selected(self):
        items = self._items()
        for row in self._selected_rows():
            if 0 <= row < len(items):
                items.pop(row)
        self._save(items)
        self._reload()

    def _toggle_selected(self):
        items = self._items()
        for row in sorted({i.row() for i in self.list.selectedIndexes()}):
            if 0 <= row < len(items):
                items[row]["done"] = not items[row].get("done", False)
        self._save(items)
        self._reload()

    def _clear_done(self):
        self._save([it for it in self._items() if not it.get("done")])
        self._reload()

    def _on_item_changed(self, item):
        if self._loading:
            return
        self._loading = True
        items = self._items()
        row = self.list.row(item)
        if 0 <= row < len(items):
            items[row]["done"] = item.checkState() == Qt.CheckState.Checked
            self._save(items)
            self._reload()
        self._loading = False


class Feature:
    id = "feature.todo"
    name = "待办清单"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("待办清单", self._open)
        self._daily_report()

    def _open(self):
        win = self.ctx.data.get("win")
        if win is None:
            win = TodoWindow(self.ctx)
            self.ctx.data["win"] = win
        if win.isVisible():
            win.raise_()
        else:
            win.show()

    def _daily_report(self):
        """每天首次加载报一次未完成数。"""
        today = time.strftime("%Y-%m-%d")
        if self.ctx.get_state("todo.last_day") == today:
            return
        self.ctx.set_state("todo.last_day", today)
        undone = [it for it in (self.ctx.get_state("todo.items") or [])
                  if isinstance(it, dict) and not it.get("done")]
        if undone:
            self.ctx.say("你有 %d 件事没做完。……我可都记着呢。" % len(undone))
        self.ctx.emit("feature.todo.daily", {"undone": len(undone)})
