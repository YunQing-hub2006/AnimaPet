# -*- coding: utf-8 -*-
"""动画播放器: 帧状态机。从 YingPet-v4 core/animator.py 原样搬运。

模式: idle(待机) / expr(表情) / anim(整段动画); 气泡打字时强制说话动画。
只负责"往 QLabel 上画哪一帧", 不知道任何业务(聊天/规则/菜单)。
依赖全部注入: label / registry / bus(仅 emit) / display_size。
"""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from anima.events import EventNames
from anima.utils import log

_log = log.get("animator")


class Animator:
    def __init__(self, label, registry, bus, display_size):
        self.label = label
        self.registry = registry
        self.bus = bus
        self.display_size = display_size

        self.mode = "idle"          # idle / expr / anim
        self.frame_idx = 0
        self.expr_frame_idx = 0
        self.current_emote = ""
        self.current_anim_id = ""
        self.idle_frames = []
        self.talk_frames = []
        self.play_frames = []
        self._emote_pm_cache = {}

        self.is_talking = lambda: False   # 由窗口注入(气泡打字中)

        self.anim_timer = QTimer(label)
        self.anim_timer.setInterval(80)
        self.anim_timer.timeout.connect(self.advance)
        self.anim_timer.start()
        self.expr_timer = QTimer(label)
        self.expr_timer.setSingleShot(True)
        self.expr_timer.timeout.connect(self.back_to_idle)

    # ------------------------------------------------------------------
    # 帧源
    # ------------------------------------------------------------------

    def set_size(self, display_size):
        self.display_size = display_size
        self._emote_pm_cache = {}

    def set_frames(self, idle_frames, talk_frames):
        """热重载/换角色/换尺寸后重置帧源。"""
        self.idle_frames = list(idle_frames or [])
        self.talk_frames = list(talk_frames or []) or list(self.idle_frames)
        self._emote_pm_cache = {}
        self.back_to_idle()

    # ------------------------------------------------------------------
    # 表现 API (规则引擎 / 功能插件 / 窗口菜单使用)
    # ------------------------------------------------------------------

    def set_emotion(self, emote_id, after_ms=0):
        if after_ms > 0:
            QTimer.singleShot(int(after_ms), lambda: self._set_emotion_now(emote_id))
        else:
            self._set_emotion_now(emote_id)

    def _set_emotion_now(self, emote_id):
        try:
            emote_id = str(emote_id)
            if emote_id == "default":
                self.back_to_idle()
                return
            e = self.registry.emote(emote_id)
            if e is None:
                _log.warning("emote not found: %s", emote_id)
                self.back_to_idle()
                return
            has_anim = bool(e.anim) and self.registry.anim(e.anim) is not None
            has_img = bool(e.image) and self._emote_image(e) is not None
            if not (has_anim or has_img):
                self.back_to_idle()
                return
            self.current_emote = emote_id
            self.mode = "expr"
            self.expr_frame_idx = 0
            self.expr_timer.start(max(500, int(e.hold_ms)))
            self.bus.emit(EventNames.EMOTE_SHOWN, {"emote": emote_id})
        except Exception as ex:
            _log.warning("set_emotion: %s", ex)

    def play_anim(self, anim_id, hold_ms=3000):
        """直接播一段动画(不经过情绪定义), 播完回待机。"""
        anim = self.registry.anim(str(anim_id))
        if anim is None:
            return
        self.play_frames = anim.frames(self.display_size)
        self.current_anim_id = str(anim_id)
        self.mode = "anim"
        self.expr_frame_idx = 0
        self.expr_timer.start(max(500, int(hold_ms)))

    def back_to_idle(self):
        self.mode = "idle"
        self.frame_idx = 0
        self.current_emote = ""
        self.current_anim_id = ""

    # ------------------------------------------------------------------
    # 帧状态机
    # ------------------------------------------------------------------

    def advance(self):
        try:
            if self.is_talking():
                frames, interval = self.talk_frames, 120
            elif self.mode == "expr":
                if self._advance_emote():
                    return
                frames, interval = self.idle_frames, 80
            elif self.mode == "anim" and self.play_frames:
                self._paint_loop(self.play_frames, 90)
                return
            else:
                frames, interval = self.idle_frames, 80
            self._set_interval(interval)
            if not frames:
                return
            self.frame_idx = (self.frame_idx + 1) % len(frames)
            self.label.setPixmap(frames[self.frame_idx])
        except Exception as e:
            _log.warning("advance frame: %s", e)

    def _advance_emote(self):
        """expr 模式: 优先动画帧, 其次静态图。返回 True = 已自绘。"""
        e = self.registry.emote(self.current_emote)
        anim = self.registry.anim(e.anim) if e and e.anim else None
        if anim:
            self._paint_loop(anim.frames(self.display_size), 90)
            return True
        if e and e.image:
            pm = self._emote_image(e)
            if pm is not None:
                self.label.setPixmap(pm)
                self._set_interval(80)
                return True
        return False

    def _paint_loop(self, frames, interval):
        if not frames:
            return
        self.expr_frame_idx = (self.expr_frame_idx + 1) % len(frames)
        self.label.setPixmap(frames[self.expr_frame_idx])
        self._set_interval(interval)

    def _set_interval(self, ms):
        if self.anim_timer.interval() != ms:
            self.anim_timer.setInterval(ms)

    def _emote_image(self, e):
        key = (e.owner_dir, e.image, self.display_size)
        pm = self._emote_pm_cache.get(key)
        if pm is not None:
            return pm
        path = os.path.join(e.owner_dir, e.image)
        try:
            pm = QPixmap(path)
            if pm.isNull():
                pm = None
            else:
                pm = pm.scaled(
                    self.display_size, self.display_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        except Exception:
            pm = None
        self._emote_pm_cache[key] = pm
        return pm
