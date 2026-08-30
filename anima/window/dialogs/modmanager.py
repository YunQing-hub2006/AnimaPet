# -*- coding: utf-8 -*-
"""模组管理对话框 (自 YingPet-v4 feature.settings/dialogs.py 的 ModsDialog 平移)。

差异: 数据源从 FeatureContext 改为 module_manager 服务 + config/mod 服务;
开关保存走 config 服务; 导入/导出走 anima.mods.packer; 热重载走
``mm.rescan()``(注册表同步重建)+ ``mm.fire(mm.a_rescan())``(feature 对账)。

等待内核调度(wait_fire/wait_rescan)与统一样式来自 dialogs.common。
"""
import os
import re
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from anima.mods import loader
from anima.utils import jsonio, log, paths
from anima.window.dialogs.common import (
    apply_dialog_style, import_anim_folder, import_gif, wait_fire, wait_rescan,
)

_log = log.get("module_manager.dialogs")

_ERR_PATH_ROLE = Qt.ItemDataRole.UserRole + 1   # 树条目附加数据: 错误条目的 mods 文件夹路径


class ModsDialog(QDialog):
    """模组管理: 类型分组树 / 行内状态 / 错误置顶定位 / 行内操作 / 新建入口 / 组合过滤。"""

    _TYPE_NAMES = {"character": "角色", "anim": "动画", "emote": "表情",
                   "idle": "台词", "behavior": "行为", "feature": "功能", "ui": "皮肤"}
    _TYPE_ORDER = ("character", "anim", "emote", "idle", "behavior", "feature", "ui")

    def __init__(self, mm, parent=None):
        super().__init__(parent)
        self.mm = mm
        self.setWindowTitle("模组管理")
        self.resize(760, 620)
        apply_dialog_style(self)
        layout = QVBoxLayout(self)

        title = QLabel("模组管理")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        self.lbl_summary = QLabel("")
        layout.addWidget(self.lbl_summary)

        row_filter = QHBoxLayout()
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("搜索: 名称 / id / 简介…")
        self.ed_filter.textChanged.connect(lambda _t: self._apply_filter())
        row_filter.addWidget(self.ed_filter, 1)
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("全部类型", "")
        for t in self._TYPE_ORDER:
            self.cmb_type.addItem(self._TYPE_NAMES[t], t)
        self.cmb_type.currentIndexChanged.connect(lambda _i: self._apply_filter())
        row_filter.addWidget(self.cmb_type)
        self.cmb_state = QComboBox()
        self.cmb_state.addItem("全部状态", "all")
        self.cmb_state.addItem("只看启用", "on")
        self.cmb_state.addItem("只看禁用", "off")
        self.cmb_state.currentIndexChanged.connect(lambda _i: self._apply_filter())
        row_filter.addWidget(self.cmb_state)
        self.chk_flat = QCheckBox("全部平铺")
        self.chk_flat.toggled.connect(lambda _on: self._build_list())
        row_filter.addWidget(self.chk_flat)
        layout.addLayout(row_filter)

        self.listw = QTreeWidget()
        self.listw.setHeaderLabels(["模组（右键行 = 操作）"])
        self.listw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listw.customContextMenuRequested.connect(self._on_item_menu)
        layout.addWidget(self.listw, 1)

        self.lbl_errors = QLabel("")
        self.lbl_errors.setStyleSheet("color: #ff8080;")
        self.lbl_errors.setWordWrap(True)
        layout.addWidget(self.lbl_errors)

        layout.addLayout(self._build_bottom_row())

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._changes = {}
        self._rows = []          # [(mod_id, checkbox, tree_item)]
        self._row_meta = {}      # mod_id -> mod 对象
        self._group_nodes = {}   # type -> 顶级分组节点
        self._error_items = []   # 加载失败条目(置顶)
        self._build_list()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    def _build_bottom_row(self):
        row = QHBoxLayout()
        self.btn_new = QPushButton("新建…")
        self.menu_new = QMenu(self.btn_new)
        self.act_import_anim = QAction("导入 PNG 序列帧到素材库…", self)
        self.act_import_anim.triggered.connect(self._import_anim)
        self.menu_new.addAction(self.act_import_anim)
        self.act_import_gif = QAction("导入 GIF 动画到素材库…", self)
        self.act_import_gif.triggered.connect(self._import_gif)
        self.menu_new.addAction(self.act_import_gif)
        self.act_new_rule = QAction("新建规则模板…", self)
        self.act_new_rule.triggered.connect(self._open_new_rule_dialog)
        self.menu_new.addAction(self.act_new_rule)
        self.act_new_feature = QAction("新建功能模组…", self)
        self.act_new_feature.triggered.connect(self._open_new_feature_dialog)
        self.menu_new.addAction(self.act_new_feature)
        self.btn_new.setMenu(self.menu_new)
        row.addWidget(self.btn_new)
        self.btn_open = QPushButton("打开 mods 文件夹")
        self.btn_open.clicked.connect(lambda: self.mm.open_path(paths.MODS_DIR))
        row.addWidget(self.btn_open)
        self.btn_export_log = QPushButton("导出日志…")
        self.btn_export_log.clicked.connect(self._export_log)
        row.addWidget(self.btn_export_log)
        self.btn_open_log = QPushButton("打开日志文件夹")
        self.btn_open_log.clicked.connect(lambda: self.mm.open_path(paths.DATA_DIR))
        row.addWidget(self.btn_open_log)
        row.addStretch(1)
        self.btn_all = QPushButton("全部启用")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        row.addWidget(self.btn_all)
        self.btn_none = QPushButton("全部禁用")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(self.btn_none)
        self.btn_refresh = QPushButton("重新扫描")
        self.btn_refresh.clicked.connect(self._rescan)
        row.addWidget(self.btn_refresh)
        return row

    @staticmethod
    def _mod_type(m):
        """从模组对象类型判定 type, 不能靠 id 前缀。"""
        for cls, t in ((loader.CharacterMod, "character"), (loader.AnimMod, "anim"),
                       (loader.EmoteDef, "emote"), (loader.IdlePack, "idle"),
                       (loader.BehaviorMod, "behavior"), (loader.FeatureMod, "feature"),
                       (loader.UiMod, "ui")):
            if isinstance(m, cls):
                return t
        return m.id.split(".")[0] if "." in m.id else "?"

    def _build_list(self):
        self.listw.clear()
        self._rows = []
        self._row_meta = {}
        self._group_nodes = {}
        self._error_items = []
        enabled = self.mm.config.get("mods.enabled", {})
        flat = self.chk_flat.isChecked()
        errors = self.mm.registry.errors

        # 错误模组置顶(可展开查看具体错误; 右键可打开所在文件夹)
        if errors:
            if flat:
                for dirname, msg in errors:
                    self._add_error_item("✗ 加载失败: %s — %s" % (dirname, msg),
                                         os.path.join(paths.MODS_DIR, dirname))
            else:
                err_node = QTreeWidgetItem(["✗ 加载失败 (%d)" % len(errors)])
                err_node.setForeground(0, QColor("#ff8080"))
                self.listw.addTopLevelItem(err_node)
                for dirname, msg in errors:
                    it = QTreeWidgetItem(["%s — %s" % (dirname, msg)])
                    it.setForeground(0, QColor("#ff8080"))
                    err_node.addChild(it)
                    self._error_items.append(it)
                    it.setData(0, _ERR_PATH_ROLE, os.path.join(paths.MODS_DIR, dirname))
                err_node.setExpanded(True)

        if not flat:
            for t in self._TYPE_ORDER:
                node = QTreeWidgetItem(["%s (0)" % self._TYPE_NAMES[t]])
                node.setData(0, Qt.ItemDataRole.UserRole, "__group__:" + t)
                self.listw.addTopLevelItem(node)
                self._group_nodes[t] = node

        for m in self.mm.registry.all_mods:
            self._add_mod_row(m, enabled, flat)

        if not flat:
            for node in self._group_nodes.values():
                node.setExpanded(True)
        self._apply_filter()
        self._update_summary()

    def _add_error_item(self, text, folder):
        it = QTreeWidgetItem([text])
        it.setForeground(0, QColor("#ff8080"))
        it.setData(0, Qt.ItemDataRole.UserRole, "")
        self.listw.addTopLevelItem(it)
        self._error_items.append(it)
        it.setData(0, _ERR_PATH_ROLE, folder)
        return it

    def _add_mod_row(self, m, enabled, flat):
        t = self._mod_type(m)
        tname = self._TYPE_NAMES.get(t, t)
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, m.id)
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(row_w)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(1)
        cb = QCheckBox("[%s] %s" % (tname, getattr(m, "name", "") or m.id))
        cb.setStyleSheet("font-weight: bold;")
        cb.setChecked(bool(enabled.get(m.id, True)))
        cb.toggled.connect(lambda on, mid=m.id: self._mark(mid, on))
        v.addWidget(cb)
        ver = str(getattr(m, "version", "") or "")
        desc = str(getattr(m, "description", "") or "")
        sub_text = m.id
        if ver:
            sub_text += "  ·  v" + ver
        if desc:
            sub_text += "  ·  " + desc
        sub = QLabel(sub_text)
        sub.setStyleSheet("color: #a08cb0; font-size: 11px;")
        sub.setWordWrap(True)
        v.addWidget(sub)
        item.setSizeHint(0, row_w.sizeHint())
        if flat:
            self.listw.addTopLevelItem(item)
        elif t in self._group_nodes:
            self._group_nodes[t].addChild(item)
        else:
            self.listw.addTopLevelItem(item)
        self.listw.setItemWidget(item, 0, row_w)
        self._rows.append((m.id, cb, item))
        self._row_meta[m.id] = m

    # ------------------------------------------------------------------
    # 状态 / 过滤
    # ------------------------------------------------------------------

    def _update_summary(self):
        cfg = self.mm.config
        char = self.mm.registry.character(str(cfg.get("mods.character", "")))
        ui = self.mm.registry.ui(str(cfg.get("mods.ui", "")))
        char_txt = ("%s (%s)" % (char.name, char.id)) if char else "无"
        ui_txt = ("%s (%s)" % (ui.name, ui.id)) if ui else "默认"
        total = len(self._rows)
        on = sum(1 for _, cb, _ in self._rows if cb.isChecked())
        self.lbl_summary.setText(
            "当前角色卡: %s ｜ 当前皮肤: %s ｜ 已启用 %d/%d 个模组" % (char_txt, ui_txt, on, total))

    def _mark(self, mid, on):
        self._changes[mid] = on
        self._apply_filter()
        self._update_summary()

    def _apply_filter(self):
        kw = self.ed_filter.text().strip().lower()
        type_sel = str(self.cmb_type.currentData() or "")
        state_sel = str(self.cmb_state.currentData() or "all")
        visible = {}
        for mid, cb, item in self._rows:
            m = self._row_meta.get(mid)
            if m is None:
                continue
            t = self._mod_type(m)
            tname = self._TYPE_NAMES.get(t, t or "")
            on = cb.isChecked()
            type_hit = (not type_sel or t == type_sel)
            state_hit = (state_sel == "all"
                         or (state_sel == "on" and on)
                         or (state_sel == "off" and not on))
            text = " ".join((m.id, str(getattr(m, "name", "") or ""),
                             str(getattr(m, "description", "") or ""), tname)).lower()
            hit = type_hit and state_hit and (not kw or kw in text)
            item.setHidden(not hit)
            if hit:
                visible[t] = visible.get(t, 0) + 1
        for t, node in self._group_nodes.items():
            node.setText(0, "%s (%d)" % (self._TYPE_NAMES.get(t, t), visible.get(t, 0)))
            node.setHidden(visible.get(t, 0) == 0)
        for it in self._error_items:
            it.setHidden(bool(kw) and kw not in it.text(0).lower())

    def _set_all(self, on):
        for _, cb, _ in self._rows:
            cb.setChecked(on)
        self._apply_filter()
        self._update_summary()

    # ------------------------------------------------------------------
    # 保存 / 重扫
    # ------------------------------------------------------------------

    def _rescan(self):
        wait_rescan(self.mm.rescan())
        self._changes = {}
        self._build_list()

    def _save(self):
        if self._changes:
            cfg = self.mm.config
            enabled = dict(cfg.get("mods.enabled", {}) or {})
            enabled.update(self._changes)
            cfg.set("mods.enabled", enabled)
            cfg.save()
        wait_rescan(self.mm.rescan())
        QMessageBox.information(self, "完成", "模组已热重载。")
        self.accept()

    # ------------------------------------------------------------------
    # 行内右键操作: 打开文件夹 / 导出模组包 / 设为当前皮肤
    # ------------------------------------------------------------------

    def _on_item_menu(self, pos):
        item = self.listw.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        err_path = item.data(0, _ERR_PATH_ROLE)
        if err_path:
            act_open = QAction("打开所在文件夹", self)
            act_open.triggered.connect(lambda _=False, p=err_path: self.mm.open_path(p))
            menu.addAction(act_open)
            menu.exec(self.listw.viewport().mapToGlobal(pos))
            return
        mid = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        m = self._row_meta.get(mid)
        if m is None:
            return
        src = getattr(m, "dir", "") or getattr(m, "owner_dir", "")
        act_open = QAction("打开所在文件夹", self)
        act_open.triggered.connect(lambda _=False, p=src: self.mm.open_path(p))
        menu.addAction(act_open)
        act_export = QAction("导出为模组包…", self)
        act_export.triggered.connect(lambda _=False, i=mid: self._export_mod(i))
        menu.addAction(act_export)
        if m.id.startswith("ui."):
            act_skin = QAction("设为当前皮肤", self)
            act_skin.triggered.connect(lambda _=False, i=mid: self._set_current_skin(i))
            menu.addAction(act_skin)
        menu.addSeparator()
        act_delete = QAction("删除模组…", self)
        act_delete.triggered.connect(lambda _=False, i=mid: self._delete_mod(i))
        menu.addAction(act_delete)
        menu.exec(self.listw.viewport().mapToGlobal(pos))

    def _delete_mod(self, mid):
        """删除模组(feature 先走内核卸载, 再删 mods/ 文件夹, 最后热重载)。"""
        m = self._row_meta.get(mid)
        name = str(getattr(m, "name", "") or mid)
        if QMessageBox.question(
                self, "删除模组",
                "确定删除模组「%s」(%s)?\n将同时删除 mods/ 下的文件夹, 不可恢复。" % (name, mid),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        fut = self.mm.fire(self.mm.delete_mod(mid))
        try:
            wait_fire(fut, timeout=10)
        except Exception as e:
            _log.warning("delete %s: %s", mid, e)
            QMessageBox.warning(self, "删除失败", str(e))
            return
        self._changes.pop(mid, None)
        self._build_list()

    def _export_mod(self, mid):
        dest, _ = QFileDialog.getSaveFileName(
            self, "导出模组包", os.path.join(paths.BASE_DIR, mid.replace(":", "_") + ".zip"),
            "ZIP 压缩包 (*.zip)")
        if not dest:
            return
        try:
            n = self.mm.export_zip(mid, dest)
            QMessageBox.information(
                self, "导出完成", "已导出 %s（%d 个文件）" % (os.path.basename(dest), n))
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _export_log(self):
        """导出 data/pet.log 到用户选择的位置。"""
        if not os.path.isfile(paths.LOG_PATH):
            QMessageBox.information(self, "导出日志",
                                    "还没有日志文件(data/pet.log 未生成)。")
            return
        default = "AnimaPet-%s.log" % time.strftime("%Y%m%d-%H%M%S")
        dest, _ = QFileDialog.getSaveFileName(
            self, "导出日志", os.path.join(paths.BASE_DIR, default),
            "日志文件 (*.log);;所有文件 (*.*)")
        if not dest:
            return
        try:
            self.mm.export_log(dest)
            QMessageBox.information(self, "导出完成",
                                    "日志已导出: %s" % os.path.basename(dest))
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _set_current_skin(self, uid):
        if self.mm.registry.ui(uid) is None:
            return
        self.mm.config.set("mods.ui", uid)
        self.mm.config.save()
        self._rescan()

    # ------------------------------------------------------------------
    # 新建入口: 导入动画 / 规则模板 / 功能模组
    # ------------------------------------------------------------------

    def _import_anim(self):
        src = QFileDialog.getExistingDirectory(self, "选择包含序列帧 PNG 的文件夹")
        if not src:
            return
        try:
            new_id, _dir = import_anim_folder(src)
            self._rescan()
            QMessageBox.information(self, "导入成功", "已导入为动画模组: " + new_id)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    def _import_gif(self):
        src, _ = QFileDialog.getOpenFileName(self, "选择 GIF 文件", "",
                                             "GIF 动画 (*.gif);;所有文件 (*.*)")
        if not src:
            return
        try:
            new_id, _dir = import_gif(src)
            self._rescan()
            QMessageBox.information(self, "导入成功",
                                    "GIF 已拆帧导入为动画模组: %s" % new_id)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    def _open_new_rule_dialog(self):
        dlg = NewRuleTemplateDialog(self.mm, self)
        dlg.exec()
        if dlg.created_id:
            self._rescan()

    def _open_new_feature_dialog(self):
        dlg = NewFeatureModDialog(self.mm, self)
        dlg.exec()
        if dlg.created_id:
            self._rescan()


class _NewModDialogBase(QDialog):
    """新建功能模组/规则模板对话框的公共骨架: id+名称 表单与校验。"""

    PREFIX = ""          # 模组 id 前缀, 如 "feature." / "behavior."
    WINDOW_TITLE = ""
    TIP = ""

    def __init__(self, mm, parent=None):
        super().__init__(parent)
        self.mm = mm
        self.created_id = ""
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(460, 220)
        apply_dialog_style(self)
        v = QVBoxLayout(self)
        form = QFormLayout()
        self.ed_id = QLineEdit()
        self.ed_id.setPlaceholderText("如 my_mod 或 %smy_mod（小写字母/数字/_.-）" % self.PREFIX)
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("显示名，如 我的模组")
        form.addRow("模组 id", self.ed_id)
        form.addRow("名称", self.ed_name)
        v.addLayout(form)
        tip = QLabel(self.TIP)
        tip.setWordWrap(True)
        v.addWidget(tip)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _base_id(self):
        """去掉可选前缀并校验, 返回短名; 不合法时弹窗并返回 None。"""
        base = self.ed_id.text().strip().lower()
        if base.startswith(self.PREFIX):
            base = base[len(self.PREFIX):]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", base or ""):
            QMessageBox.warning(self, "id 不合法", "只允许小写字母/数字/_.-，且不能以符号开头。")
            return None
        return base

    def _check_conflict(self, mid):
        taken = {m.id for m in self.mm.registry.all_mods}
        if mid in taken:
            QMessageBox.warning(self, "id 冲突", "模组已存在: " + mid)
            return False
        return True

    def _save(self):
        """子类实现: 校验通过后创建模组, 成功则 set created_id 并 accept。"""
        raise NotImplementedError


class NewFeatureModDialog(_NewModDialogBase):
    """新建功能模组: 输入 id/名称, 经 mm.create_feature_mod 生成并热启用。"""

    PREFIX = "feature."
    WINDOW_TITLE = "新建功能模组"
    TIP = "生成 Hello World 模板; 之后直接改 mods/feature.<id>/plugin.py 写自己的实现。"

    def _save(self):
        base = self._base_id()
        if base is None:
            return
        mid = "feature." + base
        if not self._check_conflict(mid):
            return
        name = self.ed_name.text().strip() or base
        try:
            fut = self.mm.fire(self.mm.create_feature_mod(mid, name))
            wait_fire(fut, 10)
        except Exception as e:
            QMessageBox.warning(self, "创建失败", str(e))
            return
        self.created_id = mid
        self.accept()


class NewRuleTemplateDialog(_NewModDialogBase):
    """新建行为规则模板: 生成一个带示例规则的 behavior.* 模组(全局规则)。"""

    PREFIX = "behavior."
    WINDOW_TITLE = "新建规则模板"
    TIP = "生成带示例规则的 behavior.* 模组。\n提示: 角色专属规则请在「角色卡管理器 → 行为」里编辑。"

    def _save(self):
        base = self._base_id()
        if base is None:
            return
        mid = "behavior." + base
        if not self._check_conflict(mid):
            return
        name = self.ed_name.text().strip() or base
        d = os.path.join(paths.MODS_DIR, mid)
        try:
            os.makedirs(d, exist_ok=True)
            jsonio.save(os.path.join(d, "manifest.json"), {
                "id": mid, "type": "behavior", "version": "1.0.0",
                "name": name, "description": "新建的规则模板",
                "rules": [{
                    "on": "timer.idle",
                    "cooldown": 600,
                    "when": "rand < 0.5",
                    "then": [{"say": "（把这里换成你的规则台词）"}],
                }],
            })
            wait_rescan(self.mm.rescan())
            self.created_id = mid
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "创建失败", str(e))
