# -*- coding: utf-8 -*-
"""新建角色卡向导(3 步): 信息 → 动画 → 确认。生成自包含 card.* 文件夹并热切换。"""
import os
import re

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from anima.utils import jsonio, log, paths
from . import wait_rescan

_log = log.get("feature.charcard.wizard")

WHITE_STYLE = (
    "QDialog { background: #ffffff; color: #111111; }"
    "QLabel { background: transparent; color: #111111; }"
    "QLineEdit, QPlainTextEdit, QComboBox { background: #ffffff; color: #111111;"
    " border: 1px solid #b0b0b0; border-radius: 3px; padding: 4px 6px; }"
    "QPushButton { background: #f2f2f2; color: #111111; border: 1px solid #b0b0b0;"
    " border-radius: 3px; padding: 4px 12px; }"
    "QPushButton:hover { background: #e2e2e2; }"
)


class NewCardWizard(QDialog):
    def __init__(self, mm, parent=None):
        super().__init__(parent)
        self.mm = mm
        self.registry = mm.registry
        self.created_id = ""
        self._base = ""
        self.setWindowTitle("新建角色卡")
        self.resize(560, 460)
        self.setStyleSheet(WHITE_STYLE)

        root = QVBoxLayout(self)
        self.stack = QStackedWidget()

        # 第 1 步: 基础信息
        p1 = QWidget()
        v1 = QVBoxLayout(p1)
        form = QFormLayout()
        self.ed_id = QLineEdit()
        self.ed_id.setPlaceholderText("如 mio 或 card.mio（只含小写字母/数字/_.-）")
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("角色显示名")
        self.ed_desc = QLineEdit()
        self.ed_desc.setPlaceholderText("一句话描述(可空)")
        form.addRow("角色卡 id", self.ed_id)
        form.addRow("名称", self.ed_name)
        form.addRow("描述", self.ed_desc)
        v1.addLayout(form)
        v1.addWidget(QLabel("system_prompt 人设"))
        self.ed_prompt = QPlainTextEdit()
        v1.addWidget(self.ed_prompt, 1)
        self.stack.addWidget(p1)

        # 第 2 步: 动画(可引用公共素材库, 也可稍后导入卡内)
        p2 = QWidget()
        v2 = QVBoxLayout(p2)
        form2 = QFormLayout()
        self.cmb_idle = QComboBox()
        self.cmb_talk = QComboBox()
        for cmb in (self.cmb_idle, self.cmb_talk):
            cmb.addItem("（稍后设置，使用兜底动画）", "")
            for aid, a in sorted(self.registry.anims.items()):
                cmb.addItem("%s  (%s)" % (aid, a.name), aid)
        form2.addRow("待机动画", self.cmb_idle)
        form2.addRow("说话动画", self.cmb_talk)
        v2.addLayout(form2)
        tip2 = QLabel("可不选：核心会自动回退到第一个可用动画。\n"
                      "之后可以在角色卡管理器里把 PNG 序列帧直接导入卡内。")
        tip2.setStyleSheet("color: #777777;")
        v2.addWidget(tip2)
        v2.addStretch(1)
        self.stack.addWidget(p2)

        # 第 3 步: 确认
        p3 = QWidget()
        v3 = QVBoxLayout(p3)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        v3.addWidget(self.lbl_summary)
        v3.addStretch(1)
        self.stack.addWidget(p3)

        root.addWidget(self.stack, 1)
        row = QHBoxLayout()
        self.btn_back = QPushButton("上一步")
        self.btn_back.clicked.connect(self._back)
        self.btn_next = QPushButton("下一步")
        self.btn_next.clicked.connect(self._next)
        self.btn_finish = QPushButton("完成并热切换")
        self.btn_finish.clicked.connect(self._finish)
        row.addWidget(self.btn_back)
        row.addStretch(1)
        row.addWidget(self.btn_next)
        row.addWidget(self.btn_finish)
        root.addLayout(row)
        self._step = 0
        self._sync_buttons()

    def _sync_buttons(self):
        self.btn_back.setEnabled(self._step > 0)
        self.btn_next.setVisible(self._step < 2)
        self.btn_finish.setVisible(self._step == 2)

    def _next(self):
        if self._step == 0 and not self._validate_step1():
            return
        if self._step == 1:
            self._update_summary()
        self._step += 1
        self.stack.setCurrentIndex(self._step)
        self._sync_buttons()

    def _back(self):
        if self._step > 0:
            self._step -= 1
            self.stack.setCurrentIndex(self._step)
            self._sync_buttons()

    def _validate_step1(self):
        base = self.ed_id.text().strip().lower()
        if base.startswith("card."):
            base = base[5:]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", base or ""):
            QMessageBox.warning(self, "角色卡 id 不合法",
                                "id 只能包含小写字母/数字/_.-，且不能以符号开头。")
            return False
        if not self.ed_name.text().strip():
            QMessageBox.warning(self, "缺少名称", "请填写角色名称。")
            return False
        self._base = base
        cid = "card." + base
        taken = {m.id for m in self.registry.all_mods}
        if cid in taken or os.path.isdir(os.path.join(paths.MODS_DIR, cid)):
            QMessageBox.warning(self, "id 冲突", "角色卡已存在: " + cid)
            return False
        return True

    def _update_summary(self):
        cid = "card." + self._base
        self.lbl_summary.setText(
            "即将创建自包含角色卡:\n"
            "  mods/%s/\n"
            "    manifest.json   人设 + 动画引用\n"
            "    emotes.json     表情(含 default)\n"
            "    idle.json       空闲台词包\n"
            "    behaviors.json  行为规则(含摸头示例)\n"
            "    anims/          卡内动画(之后导入)\n\n"
            "完成后自动热重载并切换为该角色。" % cid)

    def _finish(self):
        if self._step != 2:
            return
        cid = "card." + self._base
        name = self.ed_name.text().strip()
        desc = self.ed_desc.text().strip()
        prompt = self.ed_prompt.toPlainText().strip() or "（%s，新角色，待填写人设）" % name
        idle_anim = str(self.cmb_idle.currentData() or "")
        talk_anim = str(self.cmb_talk.currentData() or "")
        d = os.path.join(paths.MODS_DIR, cid)
        try:
            os.makedirs(os.path.join(d, "anims"), exist_ok=True)
            jsonio.save(os.path.join(d, "manifest.json"), {
                "id": cid, "type": "card", "version": "1.0.0",
                "name": name, "description": desc,
                "idle_anim": idle_anim, "talk_anim": talk_anim,
                "system_prompt": prompt,
            })
            jsonio.save(os.path.join(d, "emotes.json"), {
                "emotes": {
                    "default": {"name": "平时", "image": "", "anim": "",
                                "hold_ms": 4000,
                                "lines": ["……", "（%s 的默认台词，可在角色卡管理器里修改）" % name]},
                },
            })
            jsonio.save(os.path.join(d, "idle.json"), {
                "interval_min": 180, "interval_max": 420,
                "lines": {"default": ["……", "今天也很安静。"]},
            })
            jsonio.save(os.path.join(d, "behaviors.json"), {
                "rules": [{
                    "on": "pet.petted", "cooldown": 2,
                    "then": [{"say": "@idle.this.default"}],
                }],
            })
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))
            return
        self.mm.config.set("mods.character", cid)
        self.mm.config.save()
        wait_rescan(self.mm.rescan())
        self.created_id = cid
        self.accept()
