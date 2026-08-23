# -*- coding: utf-8 -*-
"""角色卡管理器共用组件: 动画预览盒 + 动画导入工具。"""
import os
import re
import shutil

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout,
)

from anima.utils import jsonio, paths


# ----------------------------------------------------------------------
# 动画导入
# ----------------------------------------------------------------------

def _pngs(src):
    return sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))


def import_anim_to_library(src):
    """PNG 文件夹 → 公共素材库 anim.* 模组。返回 (new_id, mod_dir)。"""
    files = _pngs(src)
    if not files:
        raise ValueError("所选文件夹里没有 PNG 文件。")
    base = re.sub(r"[^\w一-鿿-]+", "_", os.path.basename(src)).strip("_") or "anim"
    name = base
    i = 1
    while os.path.isdir(os.path.join(paths.MODS_DIR, "anim." + name)):
        i += 1
        name = "%s_%d" % (base, i)
    mid = "anim." + name
    d = os.path.join(paths.MODS_DIR, mid)
    os.makedirs(os.path.join(d, "frames"), exist_ok=True)
    for f in files:
        shutil.copy2(os.path.join(src, f), os.path.join(d, "frames", f))
    jsonio.save(os.path.join(d, "manifest.json"), {
        "id": mid, "type": "anim", "version": "1.0.0",
        "name": name, "fps": 12, "frames_dir": "frames",
        "description": "导入的动画(公共素材库)",
    })
    return mid, d


def import_anim_to_card(card_dir, src):
    """PNG 文件夹 → 角色卡内 anims/<短名>/frames。返回短名。"""
    files = _pngs(src)
    if not files:
        raise ValueError("所选文件夹里没有 PNG 文件。")
    base = re.sub(r"[^\w一-鿿-]+", "_", os.path.basename(src)).strip("_").lower() or "anim"
    name = base
    i = 1
    while os.path.isdir(os.path.join(card_dir, "anims", name)):
        i += 1
        name = "%s_%d" % (base, i)
    d = os.path.join(card_dir, "anims", name)
    os.makedirs(os.path.join(d, "frames"), exist_ok=True)
    for f in files:
        shutil.copy2(os.path.join(src, f), os.path.join(d, "frames", f))
    return name


# ----------------------------------------------------------------------
# 动画预览盒
# ----------------------------------------------------------------------

class PreviewBox(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("动画预览", parent)
        self.frames = []
        self.frame_idx = 0
        self.playing = False

        layout = QVBoxLayout(self)
        self.canvas = QLabel("请选择一套动画")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(240, 240)
        self.canvas.setStyleSheet(
            "QLabel { background: #fafafa; color: #888888; border: 1px solid #c0c0c0; }"
        )
        layout.addWidget(self.canvas, 1)

        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setCheckable(True)
        self.btn_play.toggled.connect(self._toggle_play)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(QLabel("帧:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._on_slider)
        ctrl.addWidget(self.slider, 1)
        ctrl.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(10)
        self.spin_fps.valueChanged.connect(self._on_fps_changed)
        ctrl.addWidget(self.spin_fps)
        layout.addLayout(ctrl)

        self.lbl_info = QLabel("0 帧")
        self.lbl_info.setStyleSheet("color: #666666;")
        layout.addWidget(self.lbl_info)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)

    def set_frames(self, frames):
        self.stop()
        self.frames = list(frames or [])
        self.frame_idx = 0
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(self.frames) - 1))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.lbl_info.setText("%d 帧" % len(self.frames))
        self._draw()

    def _draw(self):
        if not self.frames:
            self.canvas.setText("无帧")
            return
        self.canvas.setPixmap(self.frames[self.frame_idx])

    def _next_frame(self):
        if not self.frames:
            return
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        self.slider.blockSignals(True)
        self.slider.setValue(self.frame_idx)
        self.slider.blockSignals(False)
        self._draw()

    def _on_slider(self, v):
        self.frame_idx = v
        self._draw()

    def _on_fps_changed(self):
        if self.playing:
            self.timer.start(int(1000 / max(1, self.spin_fps.value())))

    def _toggle_play(self, on):
        self.playing = on
        if on:
            if not self.frames:
                self.btn_play.setChecked(False)
                return
            self.btn_play.setText("⏸ 暂停")
            self.timer.start(int(1000 / max(1, self.spin_fps.value())))
        else:
            self.btn_play.setText("▶ 播放")
            self.timer.stop()

    def stop(self):
        self.playing = False
        self.timer.stop()
        self.btn_play.setChecked(False)
        self.btn_play.setText("▶ 播放")
