# -*- coding: utf-8 -*-
"""bridge 插件: TD1 双线程桥 —— 内核线程 ↔ Qt 主线程 的唯一封送通道。

服务名 ``"bridge"``。持有 PetWindow(Qt 主线程创建, 由 main.py 构造时传入):

- ``run_on_ui(fn, *a, **kw)``: 已在 Qt 主线程则直调, 否则经 QObject +
  pyqtSignal(object) 队列封送到主线程执行(TD1-A 唯一合法跨线程 UI 通道);
- ``say/emote/play_anim``: 表现 API, 供功能模组与模块管理器使用;
- ``add_menu(owner, label, cb) / remove_menu(owner)``: 右键菜单"功能"子菜单
  持久登记(按 owner=模组 id 分组), 每次变更同步重建 ``window.feature_menu``,
  功能模组卸载后菜单自动消失;
- enable 阶段把窗口接入 actions 服务(注册 say/emote/anim 动作, 文本经
  rule_engine.render_text 插值)并注入规则引擎引用, 再触发一次注册表刷新。

线程规则(见 PLAN TD1-A): UI 线程只 emit; 内核线程动 UI 一律走 run_on_ui;
订阅只发生在插件 load/unload(内核线程)。
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from anima.core import Context, Plugin
from anima.events import EventNames
from anima.utils import log

_log = log.get("bridge")


def _is_main_thread() -> bool:
    """Qt 主线程 = 进程主线程(main.py 约定), 测试(内核跑主线程)同样成立。"""
    return threading.current_thread() is threading.main_thread()


class _UiBridge(QObject):
    """QObject 队列封送器: 信号槽跨线程投递 callable。"""

    _call = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(self._on_call)

    def post(self, job) -> None:
        self._call.emit(job)

    def _on_call(self, job) -> None:
        fn, args, kwargs = job
        try:
            fn(*args, **kwargs)
        except Exception as e:
            _log.warning("ui call %r failed: %s", getattr(fn, "__name__", fn), e)


class BridgePlugin(Plugin):
    """桥插件: provide "bridge" 服务, 窗口与内核服务在此交汇。"""

    name = "bridge"
    version = "1.0.0"
    dependencies = ["config", "state", "actions", "loader", "rule_engine"]

    def __init__(self, pet_window) -> None:
        self._win = pet_window
        self._ui = _UiBridge()
        self._ctx: Context | None = None
        self._menus: dict[str, list] = {}   # owner -> [(label, cb)]

    # -- 生命周期 ---------------------------------------------------------

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        ctx.provide("bridge", self)
        # 模组热重载 → 窗口刷新(帧源/角色/皮肤随注册表重建)
        ctx.on(EventNames.MODS_RELOADED,
               lambda _data: self.run_on_ui(self._win.refresh_from_registry))

    async def enable(self) -> None:
        """依赖就绪: 把窗口接到 actions/rule_engine, 注册表现动作并刷新。"""
        assert self._ctx is not None
        win = self._win
        win.engine = self._ctx.use("rule_engine")
        win._register_actions(self._ctx.use("actions"))
        self.run_on_ui(win.refresh_from_registry)
        _log.info("bridge enabled: window bound")

    # -- 线程封送 ---------------------------------------------------------

    def run_on_ui(self, fn, *args, **kwargs) -> None:
        """在 Qt 主线程执行 fn; 已在主线程则直调(TD1-A 约定)。"""
        if _is_main_thread():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                _log.warning("ui call %r failed: %s", getattr(fn, "__name__", fn), e)
            return
        self._ui.post((fn, args, kwargs))

    # -- 表现 API ---------------------------------------------------------

    def say(self, text, hold_ms=0):
        self.run_on_ui(self._win.say, text, hold_ms=hold_ms)

    def emote(self, emote_id, after_ms=0):
        self.run_on_ui(self._win.set_emotion, emote_id, after_ms=after_ms)

    def play_anim(self, anim_id, hold_ms=3000):
        self.run_on_ui(self._win.play_anim, anim_id, hold_ms=hold_ms)

    # -- 功能菜单登记 -----------------------------------------------------

    def add_menu(self, owner: str, label: str, callback) -> None:
        """登记菜单项(按 owner 分组, 同 owner 同 label 只保留最新回调)。"""
        items = self._menus.setdefault(str(owner), [])
        for idx, (old_label, _cb) in enumerate(items):
            if old_label == label:
                items[idx] = (label, callback)
                break
        else:
            items.append((label, callback))
        self._sync_menu()

    def remove_menu(self, owner: str) -> None:
        """移除某 owner 的全部菜单项(功能模组禁用/卸载时调用)。"""
        if self._menus.pop(str(owner), None) is not None:
            self._sync_menu()

    def _sync_menu(self) -> None:
        entries = []
        for items in self._menus.values():
            entries.extend(items)
        self.run_on_ui(self._win.set_feature_menu, entries)

    # -- 其他 -------------------------------------------------------------

    @property
    def window(self):
        """宠物窗口(供模块管理器对话框等取 parent/几何)。"""
        return self._win
