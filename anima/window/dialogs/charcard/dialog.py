# -*- coding: utf-8 -*-
"""角色卡管理器: 原「角色管理器」+「素材管理器」的统一入口。

左侧角色卡列表, 右侧六个页签:
    人设 / 动画(预览+导入卡内) / 台词 / 行为触发 / 表情(富编辑) / 素材库

铁律: 改数据 = 改 dict → jsonio.save(模组目录, source_file) → wait_rescan(mm.rescan())。
角色卡(card.*)的内容写在卡文件夹内(emotes.json/idle.json/behaviors.json/anims/),
旧式 char.* 模组的内容仍写回各自 manifest.json —— 由 loader 的 source_file 字段区分。
"""
import json
import os
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTabWidget, QVBoxLayout,
    QWidget,
)

from anima.mods import loader
from anima.utils import jsonio, log, paths
from . import assets as _default_assets, wait_rescan, wizard as _default_wizard

_log = log.get("feature.charcard.dialog")

WHITE_STYLE = (
    "QDialog { background: #ffffff; color: #111111; }"
    "QLabel { background: transparent; color: #111111; }"
    "QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #ffffff; color: #111111;"
    " border: 1px solid #b0b0b0; border-radius: 3px; padding: 4px 6px; }"
    "QListWidget { background: #ffffff; color: #111111; border: 1px solid #c0c0c0; }"
    "QListWidget::item { padding: 2px; }"
    "QListWidget::item:selected { background: #d6e4ff; color: #000000; }"
    "QCheckBox { background: transparent; color: #111111; }"
    "QPushButton { background: #f2f2f2; color: #111111; border: 1px solid #b0b0b0;"
    " border-radius: 3px; padding: 4px 12px; }"
    "QPushButton:hover { background: #e2e2e2; }"
    "QTabWidget::pane { border: 1px solid #c0c0c0; }"
    "QTabBar::tab { background: #f2f2f2; padding: 6px 14px; }"
    "QTabBar::tab:selected { background: #ffffff; font-weight: bold; }"
)


class CardManagerDialog(QDialog):
    def __init__(self, mm, parent=None, assets=None, wizard_mod=None):
        super().__init__(parent)
        self.mm = mm
        self.registry = mm.registry
        self.config = mm.config
        self.assets = assets if assets is not None else _default_assets
        self.wizard_mod = wizard_mod if wizard_mod is not None else _default_wizard
        self.current_id = ""
        self._rules_data = []           # 当前选中行为模组的规则副本
        self._loading = False

        self.setWindowTitle("角色卡管理器")
        self.resize(980, 660)
        self.setStyleSheet(WHITE_STYLE)

        root = QVBoxLayout(self)
        tip = QLabel("一张角色卡 = 人设 + 动画 + 台词 + 行为触发 + 表情。"
                     "所有修改写回卡文件夹并热重载, 即改即生效。")
        tip.setStyleSheet("color: #555555;")
        root.addWidget(tip)

        main = QHBoxLayout()
        left = QVBoxLayout()
        self.listw = QListWidget()
        self.listw.setMinimumWidth(240)
        self.listw.currentItemChanged.connect(self._on_select)
        left.addWidget(self.listw, 1)
        self.btn_new = QPushButton("新建角色卡…")
        self.btn_new.clicked.connect(self._open_wizard)
        left.addWidget(self.btn_new)
        self.btn_del = QPushButton("删除角色卡…")
        self.btn_del.clicked.connect(self._delete_character)
        left.addWidget(self.btn_del)
        main.addLayout(left, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_persona_page(), "人设")
        self.tabs.addTab(self._build_anim_page(), "动画")
        self.tabs.addTab(self._build_idle_page(), "台词")
        self.tabs.addTab(self._build_behavior_page(), "行为")
        self.tabs.addTab(self._build_emote_page(), "表情")
        self.tabs.addTab(self._build_library_page(), "素材库")
        main.addWidget(self.tabs, 3)
        root.addLayout(main, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.accept)
        root.addWidget(bb)

        self._reload_chars()

    # ==================================================================
    # 页签搭建
    # ==================================================================

    def _build_persona_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        form = QFormLayout()
        self.ed_name = QLineEdit()
        self.ed_desc = QLineEdit()
        form.addRow("名称", self.ed_name)
        form.addRow("描述", self.ed_desc)
        v.addLayout(form)
        v.addWidget(QLabel("system_prompt（人设 Prompt）"))
        self.ed_prompt = QPlainTextEdit()
        v.addWidget(self.ed_prompt, 1)
        self.btn_save_persona = QPushButton("保存人设并热重载")
        self.btn_save_persona.clicked.connect(self._save_persona)
        v.addWidget(self.btn_save_persona)
        return w

    def _build_anim_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        form = QFormLayout()
        self.cmb_idle = QComboBox()
        self.cmb_talk = QComboBox()
        self.cmb_idle.currentIndexChanged.connect(lambda _i: self._preview_combo_anim(self.cmb_idle))
        self.cmb_talk.currentIndexChanged.connect(lambda _i: self._preview_combo_anim(self.cmb_talk))
        form.addRow("待机动画", self.cmb_idle)
        form.addRow("说话动画", self.cmb_talk)
        v.addLayout(form)
        row = QHBoxLayout()
        self.btn_save_anims = QPushButton("保存动画引用并热重载")
        self.btn_save_anims.clicked.connect(self._save_anims)
        row.addWidget(self.btn_save_anims)
        self.btn_import_card_anim = QPushButton("导入 PNG 文件夹到本卡…")
        self.btn_import_card_anim.clicked.connect(self._import_anim_into_card)
        row.addWidget(self.btn_import_card_anim)
        v.addLayout(row)
        tip = QLabel("卡内动画显示为短名(存在卡文件夹 anims/ 里); 带点号的是公共素材库引用。")
        tip.setStyleSheet("color: #777777;")
        v.addWidget(tip)
        self.anim_preview = self.assets.PreviewBox()
        v.addWidget(self.anim_preview, 1)
        return w

    def _build_idle_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.lbl_idle_hint = QLabel("")
        self.lbl_idle_hint.setWordWrap(True)
        v.addWidget(self.lbl_idle_hint)
        form = QFormLayout()
        self.cmb_idle_pack = QComboBox()
        self.cmb_idle_pack.currentIndexChanged.connect(self._on_idle_pack_changed)
        self.cmb_idle_section = QComboBox()
        self.cmb_idle_section.currentIndexChanged.connect(self._on_idle_section_changed)
        self.ed_idle_lo = QLineEdit()
        self.ed_idle_hi = QLineEdit()
        form.addRow("该角色台词包", self.cmb_idle_pack)
        form.addRow("搭话间隔(秒)", self.ed_idle_lo)
        form.addRow("到(秒)", self.ed_idle_hi)
        form.addRow("编辑段名", self.cmb_idle_section)
        v.addLayout(form)
        self.ed_idle_lines = QPlainTextEdit()
        self.ed_idle_lines.setPlaceholderText(
            "每行一句台词; 段名可自由添加, 卡内行为规则用 @idle.this.<段名> 引用")
        v.addWidget(self.ed_idle_lines, 1)
        self.btn_save_idle = QPushButton("保存台词包并热重载")
        self.btn_save_idle.clicked.connect(self._save_idle)
        v.addWidget(self.btn_save_idle)
        return w

    def _build_behavior_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.lbl_beh_hint = QLabel("")
        self.lbl_beh_hint.setWordWrap(True)
        v.addWidget(self.lbl_beh_hint)
        form = QFormLayout()
        self.cmb_beh_mod = QComboBox()
        self.cmb_beh_mod.currentIndexChanged.connect(self._on_beh_mod_changed)
        form.addRow("编辑的规则", self.cmb_beh_mod)
        v.addLayout(form)
        self.rules_list = QListWidget()
        self.rules_list.currentRowChanged.connect(self._on_rule_selected)
        v.addWidget(self.rules_list, 1)
        form2 = QFormLayout()
        self.ed_rule_on = QLineEdit()
        self.ed_rule_on.setPlaceholderText("如 pet.petted / timer.idle / chat.reply")
        self.ed_rule_when = QLineEdit()
        self.ed_rule_when.setPlaceholderText("可空, 如 event.affinity % 20 == 0")
        self.ed_rule_cooldown = QLineEdit()
        self.ed_rule_cooldown.setPlaceholderText("可空, 秒")
        form2.addRow("on 触发事件", self.ed_rule_on)
        form2.addRow("when 条件", self.ed_rule_when)
        form2.addRow("cooldown 冷却", self.ed_rule_cooldown)
        v.addLayout(form2)
        v.addWidget(QLabel("then 动作 (JSON 数组, 如 "
                           '[{"say": "@idle.this.default"}, {"emote": "default"}])'))
        self.ed_rule_then = QPlainTextEdit()
        self.ed_rule_then.setMaximumHeight(110)
        v.addWidget(self.ed_rule_then)
        btns = QHBoxLayout()
        self.btn_add_rule = QPushButton("添加规则")
        self.btn_add_rule.clicked.connect(self._add_rule)
        self.btn_upd_rule = QPushButton("更新选中")
        self.btn_upd_rule.clicked.connect(self._update_rule)
        self.btn_del_rule = QPushButton("删除选中")
        self.btn_del_rule.clicked.connect(self._delete_rule)
        for b in (self.btn_add_rule, self.btn_upd_rule, self.btn_del_rule):
            btns.addWidget(b)
        v.addLayout(btns)
        self.btn_save_beh = QPushButton("保存行为规则并热重载")
        self.btn_save_beh.clicked.connect(self._save_beh)
        v.addWidget(self.btn_save_beh)
        return w

    def _build_emote_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("表情列表(当前角色可用)"))
        self.emote_list = QListWidget()
        self.emote_list.currentItemChanged.connect(self._on_emote_selected)
        lv.addWidget(self.emote_list, 1)
        row = QHBoxLayout()
        self.btn_new_emote = QPushButton("+ 新建表情")
        self.btn_new_emote.clicked.connect(self._new_emote)
        self.btn_del_emote = QPushButton("- 删除")
        self.btn_del_emote.clicked.connect(self._del_emote)
        row.addWidget(self.btn_new_emote)
        row.addWidget(self.btn_del_emote)
        lv.addLayout(row)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        form = QFormLayout()
        self.ed_emo_id = QLineEdit()
        self.ed_emo_id.setReadOnly(True)
        self.ed_emo_name = QLineEdit()
        self.cb_emo_image = QComboBox()
        self.cb_emo_image.setEditable(True)
        self.cb_emo_anim = QComboBox()
        self.cb_emo_anim.setEditable(True)
        self.spin_hold = QSpinBox()
        self.spin_hold.setRange(500, 30000)
        self.spin_hold.setSingleStep(500)
        self.spin_hold.setSuffix(" ms")
        form.addRow("ID", self.ed_emo_id)
        form.addRow("显示名", self.ed_emo_name)
        form.addRow("静态表情图", self.cb_emo_image)
        form.addRow("序列帧动画", self.cb_emo_anim)
        form.addRow("停留时长", self.spin_hold)
        rv.addLayout(form)
        self.chk_emo_owned = QCheckBox("专属当前角色(不勾 = 全局表情, 所有角色可用)")
        rv.addWidget(self.chk_emo_owned)
        rv.addWidget(QLabel("本地台词(每行一句, API 不可用时随机使用)"))
        self.ed_emo_lines = QPlainTextEdit()
        rv.addWidget(self.ed_emo_lines, 1)
        self.btn_save_emote = QPushButton("保存表情并热重载")
        self.btn_save_emote.clicked.connect(self._save_emote)
        rv.addWidget(self.btn_save_emote)
        splitter.addWidget(right)
        splitter.setSizes([300, 460])
        v.addWidget(splitter, 1)
        return w

    def _build_library_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("公共素材库 (所有角色卡都可引用的动画; 卡内动画在「动画」页签管理)"))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        self.lib_list = QListWidget()
        self.lib_list.currentItemChanged.connect(self._on_lib_selected)
        lv.addWidget(self.lib_list, 1)
        self.btn_import_lib = QPushButton("+ 导入 PNG 文件夹到素材库…")
        self.btn_import_lib.clicked.connect(self._import_anim_to_library)
        lv.addWidget(self.btn_import_lib)
        splitter.addWidget(left)
        self.lib_preview = self.assets.PreviewBox()
        splitter.addWidget(self.lib_preview)
        splitter.setSizes([340, 380])
        v.addWidget(splitter, 1)
        return w

    # ==================================================================
    # 角色卡列表
    # ==================================================================

    def _reload_chars(self, select_id=""):
        self.listw.blockSignals(True)
        self.listw.clear()
        cur = str(self.config.get("mods", {}).get("character", ""))
        want = select_id or self.current_id or cur
        for c in self.registry.characters.values():
            mark = "● " if c.id == cur else ""
            item = QListWidgetItem("%s%s  (%s)" % (mark, c.name, c.id))
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.listw.addItem(item)
            if c.id == want:
                self.listw.setCurrentItem(item)
        self.listw.blockSignals(False)
        if self.listw.currentItem() is None and self.listw.count():
            self.listw.setCurrentRow(0)
        self.current_id = ""   # 强制重载页签: registry 可能刚热重载重建过
        self._on_select(self.listw.currentItem())
        self._reload_library()

    def _on_select(self, item, _prev=None):
        cid = item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        if not cid or cid == self.current_id:
            return
        self.current_id = cid
        self._load_persona()
        self._load_anims()
        self._load_idle()
        self._load_behaviors()
        self._load_emotes()

    def _reload_and_refresh(self, keep_id):
        wait_rescan(self.mm.rescan())
        self._reload_chars(keep_id)

    def _char(self):
        return self.registry.character(self.current_id)

    def _is_card(self, c=None):
        c = c or self._char()
        return c is not None and str(c.id).startswith("card.")

    def _validate_card_or_warn(self, c):
        """保存前整体校验角色卡文件夹; 坏数据弹错误框, 不落盘。"""
        try:
            from anima.models import load_card
            load_card(c.dir)
            return True
        except ValueError as e:
            QMessageBox.warning(self, "校验失败", str(e))
            return False

    # ==================================================================
    # 人设
    # ==================================================================

    def _load_persona(self):
        c = self._char()
        if c is None:
            self.ed_name.clear()
            self.ed_desc.clear()
            self.ed_prompt.clear()
            return
        self.ed_name.setText(c.name)
        self.ed_desc.setText(c.description)
        self.ed_prompt.setPlainText(c.system_prompt)

    def _save_persona(self):
        c = self._char()
        if c is None:
            return
        c.raw["name"] = self.ed_name.text().strip() or c.name
        c.raw["description"] = self.ed_desc.text().strip()
        c.raw["system_prompt"] = self.ed_prompt.toPlainText().strip() or c.system_prompt
        if not self._validate_card_or_warn(c):
            return
        jsonio.save(os.path.join(c.dir, "manifest.json"), c.raw)
        self._reload_and_refresh(c.id)

    # ==================================================================
    # 动画
    # ==================================================================

    def _card_anims(self, cid):
        """当前卡的内置动画: {短名: 注册表 id}。"""
        prefix = cid + ":"
        return {aid[len(prefix):]: aid for aid in self.registry.anims
                if aid.startswith(prefix)}

    def _fill_anim_combo(self, combo, selected_id):
        cid = self.current_id
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("（自动回退）", "")
        for short, aid in sorted(self._card_anims(cid).items()):
            combo.addItem("卡内 · " + short, aid)
        for aid, a in sorted(self.registry.anims.items()):
            if not aid.startswith(cid + ":"):
                combo.addItem("库 · %s  (%s)" % (aid, a.name), aid)
        idx = combo.findData(selected_id)
        combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)

    def _load_anims(self):
        c = self._char()
        self._fill_anim_combo(self.cmb_idle, c.idle_anim if c else "")
        self._fill_anim_combo(self.cmb_talk, c.talk_anim if c else "")

    def _preview_combo_anim(self, combo):
        aid = str(combo.currentData() or "")
        anim = self.registry.anim(aid)
        if anim is not None:
            self.anim_preview.set_frames(anim.frames(240))

    def _save_anims(self):
        c = self._char()
        if c is None:
            return
        for field, combo in (("idle_anim", self.cmb_idle), ("talk_anim", self.cmb_talk)):
            aid = str(combo.currentData() or "")
            prefix = c.id + ":"
            if aid.startswith(prefix):
                c.raw[field] = aid[len(prefix):]   # 卡内动画存短名
            else:
                c.raw[field] = aid
        if not self._validate_card_or_warn(c):
            return
        jsonio.save(os.path.join(c.dir, "manifest.json"), c.raw)
        self._reload_and_refresh(c.id)

    def _import_anim_into_card(self):
        c = self._char()
        if c is None:
            return
        if not self._is_card(c):
            QMessageBox.information(self, "旧式角色模组",
                                    "该角色是旧式 char.* 模组, 动画请导入素材库后在上方引用。")
            return
        src = QFileDialog.getExistingDirectory(self, "选择包含序列帧 PNG 的文件夹")
        if not src:
            return
        try:
            short = self.assets.import_anim_to_card(c.dir, src)
            self._reload_and_refresh(c.id)
            QMessageBox.information(self, "导入成功",
                                    "已导入卡内动画「%s」, 可在上方下拉选用。" % short)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    # ==================================================================
    # 台词
    # ==================================================================

    def _owned_idle_packs(self):
        return [p for p in self.registry.idle_packs.values()
                if getattr(p, "character", "") == self.current_id]

    def _current_idle_pack(self):
        return self.registry.idle_packs.get(self.cmb_idle_pack.currentData())

    def _load_idle(self):
        cid = self.current_id
        self.cmb_idle_pack.blockSignals(True)
        self.cmb_idle_pack.clear()
        for p in self._owned_idle_packs():
            self.cmb_idle_pack.addItem("%s  (%s)" % (p.id, p.name), p.id)
        self.cmb_idle_pack.blockSignals(False)
        has = self.cmb_idle_pack.count() > 0
        for wdg in (self.cmb_idle_pack, self.cmb_idle_section, self.ed_idle_lo,
                    self.ed_idle_hi, self.ed_idle_lines, self.btn_save_idle):
            wdg.setEnabled(has)
        self.lbl_idle_hint.setText(
            "" if has else "该角色没有专属台词包，当前使用全局包。新建角色卡会自动附带一个。")
        self._on_idle_pack_changed()

    def _on_idle_pack_changed(self):
        p = self._current_idle_pack()
        self.cmb_idle_section.blockSignals(True)
        self.cmb_idle_section.clear()
        if p is not None:
            self.cmb_idle_section.addItems(list(p.sections))
        self.cmb_idle_section.blockSignals(False)
        self.ed_idle_lo.setText(str(p.interval_min) if p else "")
        self.ed_idle_hi.setText(str(p.interval_max) if p else "")
        self._on_idle_section_changed()

    def _on_idle_section_changed(self):
        p = self._current_idle_pack()
        sec = self.cmb_idle_section.currentText()
        lines = (p.sections.get(sec) if p else None) or []
        self.ed_idle_lines.setPlainText("\n".join(lines))

    def _save_idle(self):
        p = self._current_idle_pack()
        if p is None:
            return
        try:
            lo = min(86400, max(30, int(self.ed_idle_lo.text().strip() or p.interval_min)))
            hi = min(86400, max(30, int(self.ed_idle_hi.text().strip() or p.interval_max)))
        except (TypeError, ValueError):
            lo, hi = p.interval_min, p.interval_max
        p.raw["interval_min"], p.raw["interval_max"] = lo, hi
        lines = [s.strip() for s in self.ed_idle_lines.toPlainText().splitlines() if s.strip()]
        sections = p.raw.setdefault("lines", {})
        sections[self.cmb_idle_section.currentText()] = lines
        c = self._char()
        if c is None or not self._validate_card_or_warn(c):
            return
        jsonio.save(os.path.join(p.dir, p.source_file), p.raw)
        self._reload_and_refresh(p.character or self.current_id)

    # ==================================================================
    # 行为触发
    # ==================================================================

    def _owned_behavior_mods(self):
        return [m for m in self.registry.behaviors.values()
                if getattr(m, "character", "") == self.current_id]

    def _current_beh_mod(self):
        return self.registry.behaviors.get(self.cmb_beh_mod.currentData())

    def _load_behaviors(self):
        self.cmb_beh_mod.blockSignals(True)
        self.cmb_beh_mod.clear()
        for m in self._owned_behavior_mods():
            self.cmb_beh_mod.addItem("%s  (%s)" % (m.id, m.name), m.id)
        self.cmb_beh_mod.blockSignals(False)
        has = self.cmb_beh_mod.count() > 0
        for wdg in (self.cmb_beh_mod, self.rules_list, self.btn_add_rule,
                    self.btn_upd_rule, self.btn_del_rule, self.btn_save_beh,
                    self.ed_rule_on, self.ed_rule_when, self.ed_rule_cooldown,
                    self.ed_rule_then):
            wdg.setEnabled(has)
        global_rules = [m for m in self.registry.behaviors.values()
                        if not getattr(m, "character", "")]
        self.lbl_beh_hint.setText(
            "该角色的专属规则只在此角色激活时触发。另有 %d 个全局规则模组(%s)，"
            "在「模组管理」里统一开关。" % (
                len(global_rules), ", ".join(m.id for m in global_rules) or "无"))
        self._on_beh_mod_changed()

    def _on_beh_mod_changed(self):
        m = self._current_beh_mod()
        self._rules_data = [dict(r) if isinstance(r, dict) else {"on": "", "then": []}
                            for r in (m.rules if m else [])]
        self._refresh_rules(0 if self._rules_data else -1)

    def _refresh_rules(self, select):
        self.rules_list.blockSignals(True)
        self.rules_list.clear()
        for i, r in enumerate(self._rules_data):
            then_n = len(r.get("then") or []) if isinstance(r.get("then"), list) else 0
            self.rules_list.addItem("#%d  on=%s  when=%s  then=%d 个动作"
                                    % (i, r.get("on", ""), r.get("when", ""), then_n))
        self.rules_list.blockSignals(False)
        if 0 <= select < self.rules_list.count():
            self.rules_list.setCurrentRow(select)
            self._on_rule_selected(select)
        else:
            self.ed_rule_on.clear()
            self.ed_rule_when.clear()
            self.ed_rule_cooldown.clear()
            self.ed_rule_then.clear()

    def _on_rule_selected(self, row):
        if row < 0 or row >= len(self._rules_data):
            return
        r = self._rules_data[row]
        self.ed_rule_on.setText(str(r.get("on", "")))
        self.ed_rule_when.setText(str(r.get("when", "")))
        self.ed_rule_cooldown.setText(str(r.get("cooldown", "")))
        self.ed_rule_then.setPlainText(
            json.dumps(r.get("then") or [], ensure_ascii=False, indent=1))

    def _rule_from_form(self):
        rule = {"on": self.ed_rule_on.text().strip() or "pet.petted"}
        when = self.ed_rule_when.text().strip()
        if when:
            rule["when"] = when
        cd = self.ed_rule_cooldown.text().strip()
        if cd:
            try:
                rule["cooldown"] = max(0, int(cd))
            except ValueError:
                pass
        then_text = self.ed_rule_then.toPlainText().strip()
        if then_text:
            try:
                then = json.loads(then_text)
                if not isinstance(then, list):
                    raise ValueError("then 必须是 JSON 数组")
                rule["then"] = then
            except ValueError as e:
                QMessageBox.warning(self, "then 格式错误", str(e))
                return None
        else:
            rule["then"] = []
        return rule

    def _add_rule(self):
        if self._current_beh_mod() is None:
            return
        rule = self._rule_from_form()
        if rule is None:
            return
        self._rules_data.append(rule)
        self._refresh_rules(select=len(self._rules_data) - 1)

    def _update_rule(self):
        row = self.rules_list.currentRow()
        if row < 0 or row >= len(self._rules_data):
            return
        rule = self._rule_from_form()
        if rule is None:
            return
        self._rules_data[row] = rule
        self._refresh_rules(select=row)

    def _delete_rule(self):
        row = self.rules_list.currentRow()
        if 0 <= row < len(self._rules_data):
            self._rules_data.pop(row)
            self._refresh_rules(select=max(0, min(row, len(self._rules_data) - 1))
                                if self._rules_data else -1)

    def _save_beh(self):
        m = self._current_beh_mod()
        if m is not None:
            m.raw["rules"] = list(self._rules_data)
            c = self._char()
            if c is None or not self._validate_card_or_warn(c):
                return
            jsonio.save(os.path.join(m.dir, m.source_file), m.raw)
        self._reload_and_refresh(self.current_id)

    # ==================================================================
    # 表情
    # ==================================================================

    def _load_emotes(self):
        cid = self.current_id
        self.emote_list.blockSignals(True)
        self.emote_list.clear()
        for eid, e in self.registry.character_emotes(cid).items():
            owned = getattr(e, "character", "") == cid
            label = "%s  [%s]%s" % (e.name, eid, "" if owned else " (全局)")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, eid)
            self.emote_list.addItem(item)
        self.emote_list.blockSignals(False)
        if self.emote_list.count():
            self.emote_list.setCurrentRow(0)

    def _current_emote(self):
        item = self.emote_list.currentItem()
        if item is None:
            return None
        return self.registry.emote(str(item.data(Qt.ItemDataRole.UserRole)))

    def _on_emote_selected(self, item, _prev=None):
        e = self._current_emote()
        if e is None:
            return
        self._loading = True
        self.ed_emo_id.setText(e.id)
        self.ed_emo_name.setText(e.name)
        self.cb_emo_image.blockSignals(True)
        self.cb_emo_image.clear()
        self.cb_emo_image.addItem("(无)", "")
        for rel in self._scan_images(e.owner_dir):
            self.cb_emo_image.addItem(rel, rel)
        self.cb_emo_image.setCurrentText(e.image if e.image else "(无)")
        self.cb_emo_image.blockSignals(False)
        self.cb_emo_anim.blockSignals(True)
        self.cb_emo_anim.clear()
        self.cb_emo_anim.addItem("(无)", "")
        for aid in sorted(self.registry.anims):
            self.cb_emo_anim.addItem(aid, aid)
        self.cb_emo_anim.setCurrentText(e.anim if e.anim else "(无)")
        self.cb_emo_anim.blockSignals(False)
        self.spin_hold.blockSignals(True)
        self.spin_hold.setValue(int(e.hold_ms))
        self.spin_hold.blockSignals(False)
        self.ed_emo_lines.blockSignals(True)
        self.ed_emo_lines.setPlainText("\n".join(e.lines))
        self.ed_emo_lines.blockSignals(False)
        in_card = os.path.normpath(e.owner_dir) == os.path.normpath(
            self._char().dir) if self._char() else False
        self.chk_emo_owned.blockSignals(True)
        self.chk_emo_owned.setChecked(bool(getattr(e, "character", "")))
        self.chk_emo_owned.setEnabled(not in_card)
        self.chk_emo_owned.setText("专属当前角色(卡内表情天然专属)" if in_card
                                   else "专属当前角色(不勾 = 全局表情)")
        self.chk_emo_owned.blockSignals(False)
        self._loading = False

    @staticmethod
    def _scan_images(owner_dir):
        imgs = []
        for dp, _dn, fn in os.walk(owner_dir):
            for f in sorted(fn):
                if f.lower().endswith(".png"):
                    imgs.append(os.path.relpath(os.path.join(dp, f), owner_dir).replace("\\", "/"))
        return imgs

    def _save_emote(self):
        e = self._current_emote()
        if e is None:
            return
        img = self.cb_emo_image.currentText().strip()
        anim = self.cb_emo_anim.currentText().strip()
        fields = {
            "name": self.ed_emo_name.text().strip() or e.id,
            "image": img if img and img != "(无)" else "",
            "anim": anim if anim and anim != "(无)" else "",
            "hold_ms": self.spin_hold.value(),
            "lines": [ln.strip() for ln in self.ed_emo_lines.toPlainText().splitlines() if ln.strip()],
        }
        if "emotes" in e.raw:          # 表情包/角色卡: 写回 emotes 字典
            e.raw.setdefault("emotes", {})[e.id] = fields
        else:                          # 单表情模组: 字段在 manifest 顶层
            e.raw.update(fields)
        # 归属: 卡内表情由卡决定, 不动; 卡外表情按勾选写 character
        c = self._char()
        in_card = c is not None and os.path.normpath(e.owner_dir) == os.path.normpath(c.dir)
        if not in_card and c is not None:
            if self.chk_emo_owned.isChecked():
                e.raw["character"] = c.id
            else:
                e.raw.pop("character", None)
        if in_card and not self._validate_card_or_warn(c):
            return
        jsonio.save(os.path.join(e.owner_dir, e.source_file), e.raw)
        self._reload_and_refresh(self.current_id)

    def _new_emote(self):
        c = self._char()
        if c is None:
            return
        base = "new_emo"
        i = 1
        existing = set(self.registry.emotes.keys())
        while "%s_%d" % (base, i) in existing:
            i += 1
        key = "%s_%d" % (base, i)
        try:
            if self._is_card(c):
                path = os.path.join(c.dir, "emotes.json")
                raw = jsonio.load(path, {"emotes": {}})
                raw.setdefault("emotes", {})[key] = {
                    "name": "新表情", "image": "", "anim": "",
                    "hold_ms": 4000, "lines": ["……"],
                }
                jsonio.save(path, raw)
            else:
                d = os.path.join(paths.MODS_DIR, "emote." + key)
                os.makedirs(d, exist_ok=True)
                jsonio.save(os.path.join(d, "manifest.json"), {
                    "id": "emote." + key, "type": "emote", "version": "1.0.0",
                    "name": "新表情", "description": "新建的表情",
                    "character": c.id,
                    "image": "", "anim": "", "hold_ms": 4000, "lines": ["……"],
                })
            self._reload_and_refresh(c.id)
        except Exception as e:
            QMessageBox.warning(self, "新建失败", str(e))

    def _del_emote(self):
        e = self._current_emote()
        if e is None:
            return
        if e.id == "default":
            QMessageBox.warning(self, "不能删除", "『平时(default)』是默认表情, 不能删除。")
            return
        r = QMessageBox.question(
            self, "删除表情", "确定删除表情 '%s' [%s] 吗?" % (e.name, e.id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            if "emotes" in e.raw:      # 表情包/角色卡: 从包里移除
                e.raw.get("emotes", {}).pop(e.id, None)
                jsonio.save(os.path.join(e.owner_dir, e.source_file), e.raw)
            else:                      # 单表情模组: 删除整个模组文件夹
                if os.path.isdir(e.owner_dir):
                    shutil.rmtree(e.owner_dir)
            self._reload_and_refresh(self.current_id)
        except Exception as ex:
            QMessageBox.warning(self, "删除失败", str(ex))

    # ==================================================================
    # 素材库
    # ==================================================================

    def _reload_library(self):
        self.lib_list.blockSignals(True)
        self.lib_list.clear()
        cur = str(self.config.get("mods", {}).get("character", ""))
        for aid in sorted(self.registry.anims):
            if aid.startswith(cur + ":"):
                continue   # 当前卡的内置动画在「动画」页签管理
            anim = self.registry.anims[aid]
            tag = "卡内" if ":" in aid else "库"
            item = QListWidgetItem("[%s] %s  (%s)" % (tag, anim.name or aid, aid))
            item.setData(Qt.ItemDataRole.UserRole, aid)
            self.lib_list.addItem(item)
        self.lib_list.blockSignals(False)
        if self.lib_list.count():
            self.lib_list.setCurrentRow(0)

    def _on_lib_selected(self, item, _prev=None):
        if item is None:
            return
        anim = self.registry.anim(str(item.data(Qt.ItemDataRole.UserRole)))
        if anim is not None:
            self.lib_preview.set_frames(anim.frames(240))

    def _import_anim_to_library(self):
        src = QFileDialog.getExistingDirectory(self, "选择包含序列帧 PNG 的文件夹")
        if not src:
            return
        try:
            new_id, _d = self.assets.import_anim_to_library(src)
            wait_rescan(self.mm.rescan())
            self._reload_library()
            QMessageBox.information(self, "导入成功", "已导入为动画模组: %s" % new_id)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    # ==================================================================
    # 新建 / 删除
    # ==================================================================

    def _open_wizard(self):
        wiz = self.wizard_mod.NewCardWizard(self.mm, self)
        wiz.exec()
        if wiz.created_id:
            self._reload_chars(wiz.created_id)

    def _delete_character(self):
        cid = self.current_id
        c = self.registry.character(cid)
        if c is None:
            QMessageBox.warning(self, "删除角色卡", "请先在左侧选择一张角色卡。")
            return
        targets = []
        for m in self.registry.all_mods:
            if isinstance(m, loader.CharacterMod):
                if m.id == cid and m.dir not in targets:
                    targets.append(m.dir)
            elif isinstance(m, loader.EmoteDef):
                if getattr(m, "character", "") == cid and m.owner_dir not in targets:
                    targets.append(m.owner_dir)
            elif isinstance(m, (loader.IdlePack, loader.BehaviorMod)):
                if getattr(m, "character", "") == cid and m.dir not in targets:
                    targets.append(m.dir)
        targets = [d for d in targets if os.path.isdir(d)]
        if not targets:
            QMessageBox.information(self, "删除角色卡", "该角色名下没有可删除的专属模组文件夹。")
            return
        msg = ("将删除角色「%s」名下的 %d 个专属模组文件夹:\n%s\n\n"
               "全局模组(公共素材库)绝不删除。确定?" % (c.name, len(targets), "\n".join(targets)))
        ret = QMessageBox.question(
            self, "删除角色卡", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if ret != QMessageBox.StandardButton.Yes:
            return
        for d in targets:
            shutil.rmtree(d, ignore_errors=True)
        remaining = [x.id for x in self.registry.characters.values() if x.id != cid]
        self.mm.config.set("mods.character", remaining[0] if remaining else "")
        self.mm.config.save()
        wait_rescan(self.mm.rescan())
        self.current_id = ""
        self._reload_chars(remaining[0] if remaining else "")
