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
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from anima.mods import loader
from anima.utils import jsonio, log, paths
from anima.window.dialogs.common import apply_dialog_style
from . import assets as _default_assets, wait_rescan, wizard as _default_wizard

_log = log.get("feature.charcard.dialog")


class CardManagerDialog(QDialog):
    #: 行为规则触发事件下拉(新手版): 显示名 → 事件名; "__custom__" = 自己填
    _RULE_EVENTS = (
        ("被摸头", "pet.petted"),
        ("被拖动(开始)", "pet.drag_started"),
        ("被放下(拖完)", "pet.drag_ended"),
        ("被双击", "pet.double_clicked"),
        ("闲置搭话(到点)", "timer.idle"),
        ("久坐提醒(45 分钟)", "timer.sit"),
        ("深夜(23 点后)", "timer.night"),
        ("聊天回复后", "chat.reply"),
        ("切换角色后", "character.switched"),
        ("✎ 自己填事件名…", "__custom__"),
    )
    _CUSTOM_EVENT = "__custom__"

    #: 动作类型下拉里"原样保留"那一页的 data。
    _KIND_RAW = "__raw__"
    #: 编辑器能直接编辑的动作键。其余键(如 after_ms)编辑时原样带过去 ——
    #: 现有规则里 {"emote":"angry","after_ms":200} 很常见, 改个表情不该把延时弄丢。
    _ACTION_KEYS = ("say", "emote", "anim")
    #: 规则里由编辑器无条件接管的键; 条件键 when/if 单独处理, 其余未知键原样保留。
    _RULE_KEYS = ("on", "cooldown", "then")
    _COND_KEYS = ("when", "if")

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
        self._rule_extra = {}           # 当前规则里编辑器不认识的键, 原样写回
        self._rule_cond_key = "when"    # 当前规则用的条件键(when 还是 if)

        self.setWindowTitle("角色卡管理器")
        self.resize(980, 660)
        apply_dialog_style(self)

        root = QVBoxLayout(self)
        tip = QLabel("一张角色卡 = 人设 + 动画 + 台词 + 行为触发 + 表情。"
                     "所有修改写回卡文件夹并热重载, 即改即生效。")
        tip.setStyleSheet("color: #a08cb0;")
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
        self.btn_import_card_gif = QPushButton("导入 GIF 到本卡…")
        self.btn_import_card_gif.setToolTip("选一个 GIF 文件, 自动拆成序列帧存进这张卡")
        self.btn_import_card_gif.clicked.connect(self._import_gif_into_card)
        row.addWidget(self.btn_import_card_gif)
        v.addLayout(row)
        tip = QLabel("卡内动画显示为短名(存在卡文件夹 anims/ 里); 带点号的是公共素材库引用。")
        tip.setStyleSheet("color: #a08cb0;")
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
        """行为规则可视化编辑: 事件下拉 + 动作搭建器, 不需要写任何 JSON。

        高级用户仍可经「编辑选中规则 JSON…」直接改原始规则。
        """
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
        self.cmb_rule_on = QComboBox()
        for label, ev in self._RULE_EVENTS:
            self.cmb_rule_on.addItem(label, ev)
        self.cmb_rule_on.currentIndexChanged.connect(self._on_rule_event_changed)
        form2.addRow(self._field("什么时候触发", "宠物遇到这件事时执行下面的动作"), self.cmb_rule_on)
        self.ed_rule_on_custom = QLineEdit()
        self.ed_rule_on_custom.setPlaceholderText("自己填事件名, 如 feature.xxx.done")
        self.ed_rule_on_custom.hide()
        form2.addRow("", self.ed_rule_on_custom)
        self.ed_rule_when = QLineEdit()
        self.ed_rule_when.setPlaceholderText("留空 = 每次都触发")
        self.ed_rule_when.setToolTip(
            "进阶: 触发条件表达式, 如 event.affinity >= 10 / rand < 0.5。新手留空即可。")
        form2.addRow(self._field("触发条件", "进阶选项, 留空就是每次都触发"), self.ed_rule_when)
        self.ed_rule_cooldown = QLineEdit()
        self.ed_rule_cooldown.setPlaceholderText("留空 = 不限(建议填, 防刷屏)")
        self.ed_rule_cooldown.setToolTip("两次触发之间的最小间隔秒数")
        form2.addRow(self._field("冷却(秒)", "两次触发至少间隔多少秒, 防止刷屏"), self.ed_rule_cooldown)
        v.addLayout(form2)

        v.addWidget(QLabel("然后做什么(动作列表, 从上到下依次执行):"))
        self.lst_actions = QListWidget()
        self.lst_actions.setMaximumHeight(110)
        self.lst_actions.currentRowChanged.connect(self._on_action_selected)
        v.addWidget(self.lst_actions)

        editor = QHBoxLayout()
        self.cmb_action_kind = QComboBox()
        self.cmb_action_kind.addItem("说话", "say")
        self.cmb_action_kind.addItem("做表情", "emote")
        self.cmb_action_kind.addItem("播动画", "anim")
        # 第四页给 state_set/emit/state_inc 这类编辑器画不出来的动作:
        # 之前未知动作三个分支都不进, 下拉停在上一次的选项上, 一点"更新选中"
        # 就把原动作覆盖成那个不相干的值了。
        self.cmb_action_kind.addItem("高级动作(原样保留)", self._KIND_RAW)
        self.cmb_action_kind.currentIndexChanged.connect(self._on_action_kind_changed)
        editor.addWidget(self.cmb_action_kind)
        self.stack_action_value = QStackedWidget()
        self.cmb_action_say = QComboBox()
        self.cmb_action_say.setEditable(True)
        self.cmb_action_say.setToolTip("直接打字=说这句话; 选 @idle.this.段名=随机说该段台词")
        self.stack_action_value.addWidget(self.cmb_action_say)
        self.cmb_action_emote = QComboBox()
        self.stack_action_value.addWidget(self.cmb_action_emote)
        self.cmb_action_anim = QComboBox()
        self.stack_action_value.addWidget(self.cmb_action_anim)
        self.lbl_action_raw = QLabel()
        self.lbl_action_raw.setWordWrap(True)
        self.lbl_action_raw.setToolTip("这类动作可视化编辑器画不出来, 已原样保留; 要改请用「编辑选中规则 JSON…」。")
        self.stack_action_value.addWidget(self.lbl_action_raw)
        editor.addWidget(self.stack_action_value, 1)
        self.btn_action_add = QPushButton("＋ 添加")
        self.btn_action_add.clicked.connect(self._add_action_from_editor)
        editor.addWidget(self.btn_action_add)
        self.btn_action_update = QPushButton("更新选中")
        self.btn_action_update.clicked.connect(self._update_action_from_editor)
        editor.addWidget(self.btn_action_update)
        v.addLayout(editor)

        btns = QHBoxLayout()
        self.btn_action_del = QPushButton("删除动作")
        self.btn_action_del.clicked.connect(self._delete_action)
        self.btn_action_up = QPushButton("上移")
        self.btn_action_up.clicked.connect(lambda: self._move_action(-1))
        self.btn_action_down = QPushButton("下移")
        self.btn_action_down.clicked.connect(lambda: self._move_action(1))
        for b in (self.btn_action_del, self.btn_action_up, self.btn_action_down):
            btns.addWidget(b)
        btns.addStretch(1)
        self.btn_rule_json = QPushButton("编辑选中规则 JSON…(高级)")
        self.btn_rule_json.clicked.connect(self._edit_rule_json)
        btns.addWidget(self.btn_rule_json)
        v.addLayout(btns)

        btns2 = QHBoxLayout()
        self.btn_add_rule = QPushButton("添加规则")
        self.btn_add_rule.clicked.connect(self._add_rule)
        self.btn_upd_rule = QPushButton("更新选中规则")
        self.btn_upd_rule.clicked.connect(self._update_rule)
        self.btn_del_rule = QPushButton("删除选中规则")
        self.btn_del_rule.clicked.connect(self._delete_rule)
        for b in (self.btn_add_rule, self.btn_upd_rule, self.btn_del_rule):
            btns2.addWidget(b)
        v.addLayout(btns2)
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
        self.btn_import_lib_gif = QPushButton("+ 导入 GIF 到素材库…")
        self.btn_import_lib_gif.setToolTip("选一个 GIF 文件, 自动拆成序列帧进公共素材库")
        self.btn_import_lib_gif.clicked.connect(self._import_gif_to_library)
        lv.addWidget(self.btn_import_lib_gif)
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

    def _import_gif_into_card(self):
        c = self._char()
        if c is None:
            return
        if not self._is_card(c):
            QMessageBox.information(self, "旧式角色模组",
                                    "该角色是旧式 char.* 模组, 动画请导入素材库后在上方引用。")
            return
        src, _ = QFileDialog.getOpenFileName(self, "选择 GIF 文件", "",
                                             "GIF 动画 (*.gif);;所有文件 (*.*)")
        if not src:
            return
        try:
            short = self.assets.import_gif_to_card(c.dir, src)
            self._reload_and_refresh(c.id)
            QMessageBox.information(self, "导入成功",
                                    "GIF 已拆帧导入为卡内动画「%s」, 可在上方下拉选用。" % short)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    # ==================================================================
    # 台词
    # ==================================================================

    def _owned_idle_packs(self):
        return [p for p in self.registry.idle_packs.values()
                if getattr(p, "character", "") == self.current_id]

    def _current_idle_pack(self):
        # 台词包在注册表里按 <character>:<id> 命名空间收纳, 下拉里存的是裸 id
        pid = self.cmb_idle_pack.currentData()
        p = self.registry.idle_packs.get(pid)
        if p is None and pid:
            p = next((x for x in self.registry.idle_packs.values()
                      if x.id == pid and getattr(x, "character", "") == self.current_id),
                     None)
        return p

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
        # 行为模组按 <character>:<id> 命名空间收纳, 下拉里存的是裸 id
        bid = self.cmb_beh_mod.currentData()
        m = self.registry.behaviors.get(bid)
        if m is None and bid:
            m = next((x for x in self.registry.behaviors.values()
                      if x.id == bid and getattr(x, "character", "") == self.current_id),
                     None)
        return m

    def _load_behaviors(self):
        self.cmb_beh_mod.blockSignals(True)
        self.cmb_beh_mod.clear()
        for m in self._owned_behavior_mods():
            self.cmb_beh_mod.addItem("%s  (%s)" % (m.id, m.name), m.id)
        self.cmb_beh_mod.blockSignals(False)
        has = self.cmb_beh_mod.count() > 0
        for wdg in (self.cmb_beh_mod, self.rules_list, self.btn_add_rule,
                    self.btn_upd_rule, self.btn_del_rule, self.btn_save_beh,
                    self.cmb_rule_on, self.ed_rule_when, self.ed_rule_cooldown,
                    self.lst_actions, self.cmb_action_kind,
                    self.btn_action_add, self.btn_action_update,
                    self.btn_action_del, self.btn_action_up, self.btn_action_down,
                    self.btn_rule_json):
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

    # ------------------------------------------------------------------
    # 规则列表 ↔ 表单
    # ------------------------------------------------------------------

    @classmethod
    def _event_label(cls, ev):
        for label, name in cls._RULE_EVENTS:
            if name == ev:
                return label
        return str(ev)

    def _refresh_rules(self, select):
        self.rules_list.blockSignals(True)
        self.rules_list.clear()
        for i, r in enumerate(self._rules_data):
            then_n = len(r.get("then") or []) if isinstance(r.get("then"), list) else 0
            cd = (" · 冷却%ss" % r["cooldown"]) if r.get("cooldown") else ""
            self.rules_list.addItem("#%d  %s → %d 个动作%s"
                                    % (i, self._event_label(r.get("on", "")), then_n, cd))
        self.rules_list.blockSignals(False)
        if 0 <= select < self.rules_list.count():
            self.rules_list.setCurrentRow(select)
            self._on_rule_selected(select)
        else:
            self._load_rule_form(None)

    def _on_rule_selected(self, row):
        if 0 <= row < len(self._rules_data):
            self._load_rule_form(self._rules_data[row])

    @staticmethod
    def _events_to_text(on):
        """规则的 on(字符串或列表) → 事件输入框文本。

        rule_engine 两者都认(列表=多事件任一触发); 旧实现直接 str() 一个列表,
        会把 ["a","b"] 变成字面量 "['a', 'b']" 写回 JSON —— 事件名不存在,
        规则从此静默不触发。这里用逗号分隔表示, 保存时再拆回列表。
        """
        if isinstance(on, (list, tuple)):
            return ", ".join(str(x) for x in on)
        return str(on or "")

    @staticmethod
    def _text_to_events(text):
        """事件输入框文本 → on 的值(单个=字符串, 多个=列表)。"""
        parts = [p.strip() for p in str(text or "").split(",") if p.strip()]
        if not parts:
            return "pet.petted"
        return parts if len(parts) > 1 else parts[0]

    def _load_rule_form(self, rule):
        """把规则填进表单(rule=None 时清空, 供"添加新规则"起步)。"""
        r = rule or {}
        ev = self._events_to_text(r.get("on", ""))
        idx = self.cmb_rule_on.findData(ev)
        using_custom = idx < 0 and bool(ev)   # 空事件(新规则)默认选第一项
        if using_custom:
            self.cmb_rule_on.setCurrentIndex(self.cmb_rule_on.count() - 1)
            self.ed_rule_on_custom.show()
            self.ed_rule_on_custom.setText(ev)
        else:
            self.cmb_rule_on.setCurrentIndex(idx if rule is not None else 0)
            self.ed_rule_on_custom.hide()
            self.ed_rule_on_custom.clear()

        # 条件键 when / if 二选一: rule_engine 两个都认, 编辑器合成一个框,
        # 但要记住原规则用的是哪个, 保存时写回同一个键, 别无谓地改动文件。
        self._rule_cond_key = "when"
        cond = ""
        for k in self._COND_KEYS:
            if str(r.get(k, "") or "") != "":
                self._rule_cond_key, cond = k, str(r[k])
                break
        self.ed_rule_when.setText(cond)
        # 编辑器不认识的键(以及没用上的那个条件键)原样带回, 防止保存时丢字段。
        self._rule_extra = {k: v for k, v in r.items()
                            if k not in self._RULE_KEYS and k not in self._COND_KEYS}
        other = "if" if self._rule_cond_key == "when" else "when"
        if str(r.get(other, "") or "") != "":
            self._rule_extra[other] = r[other]

        self.ed_rule_cooldown.setText(str(r.get("cooldown", "")) if rule is not None else "")
        self._actions_data = list(r.get("then") or []) if rule is not None else []
        self._refresh_actions(select=-1)
        self._sync_say_suggestions()
        self._refresh_action_value_options()

    def _rule_on_value(self):
        """表单 → 事件名(选"自己填"时取输入框)。"""
        if self.cmb_rule_on.currentData() == self._CUSTOM_EVENT:
            return self.ed_rule_on_custom.text().strip()
        return str(self.cmb_rule_on.currentData() or "pet.petted")

    def _rule_from_form(self):
        """表单 + 动作列表 → 规则 dict(动作列表为空视为没配完, 拒绝)。"""
        rule = {"on": self._text_to_events(self._rule_on_value())}
        rule.update(getattr(self, "_rule_extra", {}))   # 编辑器不认识的键原样带回
        when = self.ed_rule_when.text().strip()
        if when:
            rule[self._rule_cond_key] = when
        cd = self.ed_rule_cooldown.text().strip()
        if cd:
            try:
                rule["cooldown"] = max(0, int(cd))
            except ValueError:
                QMessageBox.warning(self, "冷却填错了", "冷却要填整数秒, 比如 5; 不想限制就留空。")
                return None
        then = list(getattr(self, "_actions_data", []))
        if not then:
            QMessageBox.warning(
                self, "还没有加动作",
                "先在「然后做什么」里选好动作并点「＋ 添加」, 规则才知道要干什么。")
            return None
        rule["then"] = then
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

    def _edit_rule_json(self):
        """高级出口: 直接编辑选中规则的原始 JSON(校验后才生效)。"""
        row = self.rules_list.currentRow()
        if row < 0 or row >= len(self._rules_data):
            QMessageBox.information(self, "编辑 JSON", "请先在上方列表选中一条规则。")
            return
        text = json.dumps(self._rules_data[row], ensure_ascii=False, indent=1)
        out, ok = QInputDialog.getMultiLineText(
            self, "编辑规则 JSON (高级)",
            "字段: on 事件 / when 条件(可空) / cooldown 秒(可空) / then 动作数组", text)
        if not ok:
            return
        try:
            rule = json.loads(out)
            if not isinstance(rule, dict) or not str(rule.get("on", "")).strip():
                raise ValueError("必须是对象, 且 on 不能为空")
            if not isinstance(rule.get("then", []), list):
                raise ValueError("then 必须是数组")
        except ValueError as e:
            QMessageBox.warning(self, "JSON 不合法", str(e))
            return
        self._rules_data[row] = rule
        self._refresh_rules(select=row)

    # ------------------------------------------------------------------
    # 动作搭建器(then 列表的可视化编辑)
    # ------------------------------------------------------------------

    @staticmethod
    def _field(name, tip):
        lbl = QLabel(name)
        lbl.setToolTip(tip)
        return lbl

    def _on_rule_event_changed(self, _idx):
        custom = self.cmb_rule_on.currentData() == self._CUSTOM_EVENT
        self.ed_rule_on_custom.setVisible(custom)
        if custom:
            self.ed_rule_on_custom.setFocus()

    def _on_action_kind_changed(self, _idx):
        self.stack_action_value.setCurrentIndex(self.cmb_action_kind.currentIndex())

    def _sync_say_suggestions(self):
        """说话下拉给出现有台词段(@idle.this.<段>), 也可自己打字。"""
        p = self.registry.idle_packs.get(self.current_id + ":idle")
        secs = sorted((p.sections if p else {}).keys())
        self.cmb_action_say.blockSignals(True)
        self.cmb_action_say.clear()
        for s in secs:
            self.cmb_action_say.addItem("@idle.this." + s)
        self.cmb_action_say.blockSignals(False)

    def _refresh_action_value_options(self):
        """按当前角色刷新表情/动画下拉。"""
        self.cmb_action_emote.blockSignals(True)
        self.cmb_action_emote.clear()
        for eid, e in self.registry.character_emotes(self.current_id).items():
            self.cmb_action_emote.addItem("%s (%s)" % (e.name, eid), eid)
        self.cmb_action_emote.blockSignals(False)
        self.cmb_action_anim.blockSignals(True)
        self.cmb_action_anim.clear()
        for aid, a in sorted(self.registry.anims.items()):
            self.cmb_action_anim.addItem("%s (%s)" % (a.name or aid, aid), aid)
        self.cmb_action_anim.blockSignals(False)

    @classmethod
    def _action_label(cls, a):
        """动作 dict → 人话(未知类型原样显示 JSON)。"""
        if "say" in a:
            return "说话: %s" % a["say"]
        if "emote" in a:
            return "做表情: %s" % a["emote"]
        if "anim" in a:
            return "播动画: %s" % a["anim"]
        return json.dumps(a, ensure_ascii=False)

    def _refresh_actions(self, select=-1):
        self.lst_actions.blockSignals(True)
        self.lst_actions.clear()
        for a in self._actions_data:
            self.lst_actions.addItem(self._action_label(a) if isinstance(a, dict) else str(a))
        self.lst_actions.blockSignals(False)
        if 0 <= select < self.lst_actions.count():
            self.lst_actions.setCurrentRow(select)

    def _current_action(self):
        """动作列表里当前选中的 dict(没选返回空 dict)。"""
        row = self.lst_actions.currentRow()
        if 0 <= row < len(self._actions_data):
            a = self._actions_data[row]
            if isinstance(a, dict):
                return a
        return {}

    @staticmethod
    def _action_kind_of(a):
        """动作 dict → 编辑器类型; 三种都不是就是高级动作(None)。"""
        for k in ("say", "emote", "anim"):
            if k in a:
                return k
        return None

    def _action_from_editor(self, inherit=True):
        """编辑行 → 动作 dict。

        ``inherit=True``(更新选中)时只动"当前类型"那一个键, 其余键原样带过来。
        旧实现每次都造一个新 dict, 于是 {"emote":"angry","after_ms":200} 这种
        带延时的动作, 用户改个表情 after_ms 就没了(现有 6 条规则里 3 条中招),
        而且没有任何提示。新增动作不继承 —— 新动作跟选中行没关系。
        """
        kind = self.cmb_action_kind.currentData()
        if kind == self._KIND_RAW:
            return dict(self._current_action())     # 高级动作: 原样, 一个键都不动
        old = self._current_action() if inherit else {}
        out = dict(old)
        old_kind = self._action_kind_of(old)
        if old_kind != kind:
            # 换类型: 清掉旧的类型键, 非类型键(after_ms 等)继续留着
            for k in self._ACTION_KEYS:
                out.pop(k, None)
        # old_kind == kind 时直接覆盖, 键顺序不变 —— 保存出来的 JSON diff 才干净
        if kind == "say":
            out["say"] = self.cmb_action_say.currentText().strip()
        elif kind == "emote":
            out["emote"] = str(self.cmb_action_emote.currentData()
                               or self.cmb_action_emote.currentText())
        else:
            out["anim"] = str(self.cmb_action_anim.currentData()
                              or self.cmb_action_anim.currentText())
        return out

    def _action_is_empty(self, a):
        """判断编辑出来的动作是否为空(高级动作另算, 它本来就没得填)。"""
        if self.cmb_action_kind.currentData() == self._KIND_RAW:
            return False
        return not str(next(iter(a.values()), "") or "").strip()

    def _add_action_from_editor(self):
        a = self._action_from_editor(inherit=False)
        if self._action_is_empty(a):
            QMessageBox.information(self, "动作是空的", "先选好说什么/做什么表情/播哪个动画。")
            return
        self._actions_data.append(a)
        self._refresh_actions(select=len(self._actions_data) - 1)

    def _update_action_from_editor(self):
        row = self.lst_actions.currentRow()
        if row < 0 or row >= len(self._actions_data):
            QMessageBox.information(self, "更新动作", "请先在动作列表里选中一条。")
            return
        if self.cmb_action_kind.currentData() == self._KIND_RAW:
            QMessageBox.information(
                self, "这条动不了",
                "这是可视化编辑器画不出来的高级动作, 已经原样保留。\n"
                "要改它请用「编辑选中规则 JSON…(高级)」。")
            return
        a = self._action_from_editor()
        if self._action_is_empty(a):
            QMessageBox.information(self, "动作是空的", "先选好说什么/做什么表情/播哪个动画。")
            return
        self._actions_data[row] = a
        self._refresh_actions(select=row)

    def _on_action_selected(self, row):
        if not (0 <= row < len(self._actions_data)):
            return
        a = self._actions_data[row]
        if not isinstance(a, dict):
            return
        self._refresh_action_value_options()
        kind = self._action_kind_of(a)
        if kind is None:
            # state_set / state_inc / emit 这类编辑器画不出来的动作:
            # 旧代码三个分支都不进, 下拉停在上一次的选项上 —— 用户以为看到的是
            # 这条动作, 一点"更新选中"就把它覆盖成不相干的值。现在显式切到
            # "原样保留"页并把原始 JSON 显示出来。
            self.cmb_action_kind.setCurrentIndex(self.cmb_action_kind.count() - 1)
            self.lbl_action_raw.setText(json.dumps(a, ensure_ascii=False))
            return
        self.cmb_action_kind.setCurrentIndex(
            self._ACTION_KEYS.index(kind))
        if kind == "say":
            self.cmb_action_say.setCurrentText(str(a["say"]))
        elif kind == "emote":
            self._select_or_add(self.cmb_action_emote, str(a["emote"]))
        else:
            self._select_or_add(self.cmb_action_anim, str(a["anim"]))

    @staticmethod
    def _select_or_add(combo, value):
        """选中下拉里已有的项; 不在列表里就临时加一项再选中。

        旧写法 ``setCurrentIndex(max(0, idx))`` 在找不到时静默选中第 0 项,
        用户看到的表情/动画名跟实际存的不一致, 一按更新就写错了。
        """
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(value)
        if idx < 0:
            combo.addItem(value, value)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _delete_action(self):
        row = self.lst_actions.currentRow()
        if 0 <= row < len(self._actions_data):
            self._actions_data.pop(row)
            self._refresh_actions(select=min(row, len(self._actions_data) - 1))

    def _move_action(self, delta):
        row = self.lst_actions.currentRow()
        new = row + delta
        if not (0 <= row < len(self._actions_data)) or not (0 <= new < len(self._actions_data)):
            return
        self._actions_data[row], self._actions_data[new] = \
            self._actions_data[new], self._actions_data[row]
        self._refresh_actions(select=new)

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
        for key, e in self.registry.character_emotes(cid).items():
            owned = getattr(e, "character", "") == cid
            label = "%s  [%s]%s" % (e.name, e.id, "" if owned else " (全局)")
            item = QListWidgetItem(label)
            # 存注册表键(命名空间后), _current_emote 用它反查
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.emote_list.addItem(item)
        self.emote_list.blockSignals(False)
        if self.emote_list.count():
            self.emote_list.setCurrentRow(0)

    def _current_emote(self):
        item = self.emote_list.currentItem()
        if item is None:
            return None
        return self.registry.emotes.get(str(item.data(Qt.ItemDataRole.UserRole)))

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

    def _import_gif_to_library(self):
        from anima.window.dialogs.common import import_gif
        src, _ = QFileDialog.getOpenFileName(self, "选择 GIF 文件", "",
                                             "GIF 动画 (*.gif);;所有文件 (*.*)")
        if not src:
            return
        try:
            new_id, _d = import_gif(src)
            wait_rescan(self.mm.rescan())
            self._reload_library()
            QMessageBox.information(self, "导入成功",
                                    "GIF 已拆帧导入为动画模组: %s" % new_id)
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
