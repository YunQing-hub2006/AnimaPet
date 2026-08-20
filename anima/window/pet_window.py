# -*- coding: utf-8 -*-
"""宠物主窗口 (瘦身版): 只做骨架 —— 动画/气泡/拖拽/右键菜单壳/节拍事件。

改写自 YingPet-v4 core/window.py。核心铁律不变: 窗口只发事件 + 提供表现 API
(say/emote/anim), 具体反应(台词/规则)由行为模组声明, 功能(聊天/设置)由功能插件提供。

架构差异(v4 → AnimaPet):
- 五连引用改为**构造注入**: ``PetWindow(registry, bus, config, state, actions=None,
  engine=None)``, 全部由 main.py/bridge 传入共享实例(Qt 线程创建本窗口);
- 写 config 一律走 ConfigService.set()+save()(不绕道 jsonio);
- ``harness.change_state`` → ``state.change``;
- ``engine.set_character`` 由注入的规则引擎承担(未注入时为 None, 安全跳过);
- 右键菜单"功能"子菜单数据源 ``feature_menu`` 由 bridge/module_manager 同步。
"""
import random
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCursor, QGuiApplication
from PyQt6.QtWidgets import QLabel, QMenu, QWidget

from anima.events import EventNames
from anima.plugins import rule_engine
from anima.utils import log, theme
from anima.window import animator, bubble

_log = log.get("window")

PET_SIZES = {"small": 180, "medium": 240, "large": 320}


class PetWindow(QWidget):
    def __init__(self, registry, bus, config, state, actions=None, engine=None):
        super().__init__()
        self.registry = registry
        self.bus = bus
        self.config = config
        self.state = state
        self.actions = actions
        self.engine = engine

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.display_size = PET_SIZES.get(self.config.get("window.size"), 240)
        self.label = QLabel(self)
        self.resize(self.display_size, self.display_size)
        self.label.resize(self.size())

        # ---- 角色 / 动画 / 气泡 ----
        self.char = None
        self.animator = animator.Animator(self.label, self.registry, self.bus, self.display_size)
        self.bubble = bubble.Bubble(self)
        self.animator.is_talking = self.bubble.is_typing
        self.bubble.finished.connect(lambda: self.bus.emit(EventNames.BUBBLE_FINISHED))

        # ---- 节拍定时器(只发事件, 不写死反应) ----
        self.sit_timer = QTimer(self)
        self.sit_timer.timeout.connect(lambda: self.bus.emit(EventNames.TIMER_SIT))

        self.idle_talk_timer = QTimer(self)
        self.idle_talk_timer.setSingleShot(True)
        self.idle_talk_timer.timeout.connect(self._idle_tick)

        self.minute_timer = QTimer(self)
        self.minute_timer.timeout.connect(self._minute_tick)
        self.minute_timer.start(60 * 1000)

        # ---- 互动状态 ----
        self._drag_pos = None
        self._drag_moved = False
        self._night_done = False
        self.feature_menu = []   # [(label, callback)] 功能插件贡献的菜单项(由 bridge/module_manager 同步)

        if self.actions is not None:
            self._register_actions(self.actions)
        self.bus.subscribe(EventNames.CHARACTER_SWITCH,
                           lambda p: self._switch_character(str((p or {}).get("character", ""))))
        self.refresh_from_registry()
        self._arm_idle_talk()

        # 初始位置: 屏幕右下角
        screen = QGuiApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.right() - self.width() - 60, g.bottom() - self.height() - 60)

    # ------------------------------------------------------------------
    # 动作注册: 规则引擎的 then 动作 → 本窗口的表现能力
    # ------------------------------------------------------------------

    def _register_actions(self, reg=None):
        """谁提供能力谁注册 —— 窗口注册 say/emote/anim(文本经 render_text 插值)。"""
        reg = reg if reg is not None else self.actions
        if reg is None:
            return

        def _say(val, ctx, act):
            self.say(rule_engine.render_text(val, ctx, self.registry))

        def _emote(val, ctx, act):
            self.set_emotion(
                rule_engine.render_text(val, ctx, self.registry),
                after_ms=int(act.get("after_ms", 0) or 0))

        def _anim(val, ctx, act):
            self.play_anim(
                rule_engine.render_text(val, ctx, self.registry),
                hold_ms=int(act.get("hold_ms", 3000) or 3000))

        reg.register("say", _say)
        reg.register("emote", _emote)
        reg.register("anim", _anim)

    # ------------------------------------------------------------------
    # 表现 API (动作执行器 / 功能插件使用)
    # ------------------------------------------------------------------

    def say(self, text, hold_ms=0):
        self.bubble.say(text, hold_ms=hold_ms)

    def set_emotion(self, emote_id, after_ms=0):
        self.animator.set_emotion(emote_id, after_ms=after_ms)

    def play_anim(self, anim_id, hold_ms=3000):
        self.animator.play_anim(anim_id, hold_ms=hold_ms)

    # ------------------------------------------------------------------
    # 注册表刷新 (模组热重载时由 bridge/module_manager 调用)
    # ------------------------------------------------------------------

    def refresh_from_registry(self):
        reg = self.registry
        self.char = reg.character(self.config.get("mods.character", ""))
        if self.char is None and reg.characters:
            self.char = next(iter(reg.characters.values()))
        idle_id = (self.char.idle_anim if self.char else "") or self.config.get("window.idle_anim", "")
        talk_id = (self.char.talk_anim if self.char else "") or self.config.get("window.talk_anim", "")
        idle_anim = reg.anim(idle_id)
        talk_anim = reg.anim(talk_id)
        if idle_anim is None and reg.anims:
            idle_anim = next(iter(reg.anims.values()))
        if talk_anim is None:
            talk_anim = idle_anim or (next(iter(reg.anims.values())) if reg.anims else None)
        self.animator.set_size(self.display_size)
        self.animator.set_frames(
            idle_anim.frames(self.display_size) if idle_anim else [],
            talk_anim.frames(self.display_size) if talk_anim else [])
        # 同步当前角色: 规则引擎做行为归属隔离, 注册表供 @idle.this 解析
        char_id = self.char.id if self.char else ""
        if self.engine is not None:
            self.engine.set_character(char_id)
        self.registry.active_char_id = char_id
        self._apply_skin()
        if self.config.get("window.sit_reminder", True):
            self.sit_timer.start(45 * 60 * 1000)
        else:
            self.sit_timer.stop()
        _log.info("window refreshed: char=%s idle=%s talk=%s", char_id or None, idle_id, talk_id)

    def _apply_skin(self):
        """把当前皮肤模组(ui.*)主题应用到头顶气泡, 热重载即时生效。"""
        try:
            skin = self.registry.ui(self.config.get("mods.ui", ""))
            self.bubble.apply_theme(skin.theme if skin else {})
        except Exception as e:
            _log.warning("apply skin: %s", e)

    def current_theme(self):
        """当前合并主题(菜单 QSS / 插件面板共用)。"""
        skin = self.registry.ui(self.config.get("mods.ui", ""))
        return theme.merge_theme(skin.theme if skin else {})

    def _menu_qss(self):
        t = self.current_theme()
        return ("QMenu { background: %(menu_bg)s; color: %(menu_fg)s;"
                " border: 1px solid %(accent)s; }"
                "QMenu::item:selected { background: %(menu_hover)s; }") % t

    def set_feature_menu(self, entries):
        """bridge/module_manager 同步功能菜单项(仅 Qt 线程调用)。"""
        self.feature_menu = list(entries or [])

    # ------------------------------------------------------------------
    # 鼠标互动: 核心只做机制(拖动/计数), 反应交给行为模组
    # ------------------------------------------------------------------

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            if not self._drag_moved:
                self._drag_moved = True
                self.bus.emit(EventNames.PET_DRAG_STARTED)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            if not self._drag_moved:
                self._on_petted()
            else:
                self.bus.emit(EventNames.PET_DRAG_ENDED)
            self._drag_pos = None
            self._drag_moved = False
            self.bubble._reposition()
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        # 只发事件: 双击干什么(打开聊天?)由功能插件决定
        if e.button() == Qt.MouseButton.LeftButton:
            self.bus.emit(EventNames.PET_DOUBLE_CLICKED)
        super().mouseDoubleClickEvent(e)

    def _on_petted(self):
        v = int(self.state.get("affinity", 0)) + 1
        self.state.change("affinity", v)
        self.bus.emit(EventNames.PET_PETTED, {"affinity": v})

    # ------------------------------------------------------------------
    # 节拍定时器: 发事件, 不写死反应
    # ------------------------------------------------------------------

    def _arm_idle_talk(self):
        lo, hi = self.registry.idle_interval(self.char.id if self.char else "")
        self.idle_talk_timer.start(random.randint(lo, hi) * 1000)

    def _idle_tick(self):
        self.bus.emit(EventNames.TIMER_IDLE)
        self._arm_idle_talk()

    def _minute_tick(self):
        hour = time.localtime().tm_hour
        if hour >= 23 or hour < 5:
            if not self._night_done:
                self._night_done = True
                self.bus.emit(EventNames.TIMER_NIGHT)
        else:
            self._night_done = False

    # ------------------------------------------------------------------
    # 右键菜单: 骨架项 + 插件注册项
    # ------------------------------------------------------------------

    def contextMenuEvent(self, e):
        try:
            menu = QMenu(self)
            menu.setStyleSheet(self._menu_qss())

            self._add(menu, "摸摸头", self._on_petted)

            emo_menu = menu.addMenu("表情")
            for key, emo in self.registry.character_emotes(
                    self.char.id if self.char else "").items():
                self._add(emo_menu, emo.name, lambda k=key: self.set_emotion(k))

            if self.registry.characters:
                card_menu = menu.addMenu("角色卡")
                for cid, c in self.registry.characters.items():
                    mark = "● " if (self.char and cid == self.char.id) else ""
                    self._add(card_menu, mark + c.name, lambda k=cid: self._switch_character(k))

            if self.registry.uis:
                ui_menu = menu.addMenu("皮肤")
                cur_ui = self.config.get("mods.ui", "")
                for uid, u in self.registry.uis.items():
                    mark = "● " if uid == cur_ui else ""
                    self._add(ui_menu, mark + u.name, lambda k=uid: self._switch_ui(k))

            size_menu = menu.addMenu("大小")
            for key, name in [("small", "小"), ("medium", "中"), ("large", "大")]:
                cur = "● " if self.config.get("window.size") == key else ""
                self._add(size_menu, cur + name, lambda k=key: self._set_size(k))

            sit_on = self.config.get("window.sit_reminder", True)
            self._add(menu, "久坐提醒: " + ("开" if sit_on else "关"), self._toggle_sit)

            if self.feature_menu:
                feat_menu = menu.addMenu("功能")
                for label, cb in self.feature_menu:
                    self._add(feat_menu, label, cb)

            menu.addSeparator()
            self._add(menu, "退出", QGuiApplication.instance().quit)
            menu.exec(e.globalPos())
        except Exception as ex:
            _log.warning("menu: %s", ex)

    def _add(self, menu, label, fn):
        act = QAction(label, self)
        act.triggered.connect(lambda _checked=False: fn())
        menu.addAction(act)
        return act

    # ------------------------------------------------------------------
    # 菜单项行为
    # ------------------------------------------------------------------

    def _switch_character(self, char_id):
        c = self.registry.character(str(char_id))
        if c is None:
            return
        self.config.set("mods.character", c.id)
        self.config.save()
        self.char = c
        self.refresh_from_registry()
        self.bus.emit(EventNames.CHARACTER_SWITCHED, {"character": c.id})
        self.say("已切换角色卡: " + c.name)

    def _switch_ui(self, uid):
        u = self.registry.ui(uid)
        if u is None:
            return
        self.config.set("mods.ui", uid)
        self.config.save()
        self._apply_skin()
        self.bus.emit(EventNames.UI_CHANGED, {"ui": uid})
        self.say("已切换皮肤: " + u.name)

    def _set_size(self, key):
        self.config.set("window.size", key)
        self.config.save()
        self.display_size = PET_SIZES.get(key, 240)
        self.resize(self.display_size, self.display_size)
        self.label.resize(self.size())
        self.refresh_from_registry()

    def _toggle_sit(self):
        on = not bool(self.config.get("window.sit_reminder", True))
        self.config.set("window.sit_reminder", on)
        self.config.save()
        if on:
            self.sit_timer.start(45 * 60 * 1000)
        else:
            self.sit_timer.stop()

    def closeEvent(self, e):
        try:
            self.bubble.close()
        except Exception:
            pass
        super().closeEvent(e)
        # 关闭宠物窗口 = 显式退出(配合 quitOnLastWindowClosed=False:
        # 辅助窗口关闭不再带走应用, 退出权收回到这里与右键菜单)
        QGuiApplication.instance().quit()
