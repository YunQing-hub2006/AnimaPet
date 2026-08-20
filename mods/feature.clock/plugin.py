# -*- coding: utf-8 -*-
"""整点报时: 每 15 秒检查一次, 命中整点气泡报时。自 YingPet-v4 平移(无改动)。

- 菜单『整点报时(开关)』切换, 状态存 state.json, 热重载/重启不丢
- QTimer 在 on_disable 里停止, 卸载干净
"""
import time

from PyQt6.QtCore import QTimer


class Feature:
    id = "feature.clock"
    name = "整点报时"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("整点报时(开关)", self._toggle)
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(15000)   # 15 秒查一次, 整点窗口内必然命中
        ctx.data["clock.last_hour"] = time.localtime().tm_hour
        ctx.log("已加载")

    def on_disable(self):
        if getattr(self, "_timer", None):
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

    def _enabled(self):
        # 未设置时 None → 默认开; 显式 False → 关
        return self.ctx.get_state("clock.enabled") is not False

    def _toggle(self):
        self.ctx.set_state("clock.enabled", not self._enabled())
        self.ctx.say("整点报时已%s。" % ("开启" if self._enabled() else "关闭"))

    def _tick(self):
        if not self._enabled():
            return
        now = time.localtime()
        last = self.ctx.data.get("clock.last_hour")
        if now.tm_min == 0 and last != now.tm_hour:
            self.ctx.data["clock.last_hour"] = now.tm_hour
            self.ctx.say(_hour_text(now.tm_hour))
            self.ctx.emit("feature.clock.hourly", {"hour": now.tm_hour})


def _hour_text(hour):
    """按时段生成报时台词(独立函数, 方便单测)。"""
    if hour == 0:
        return "零点了。……还不睡吗?"
    if hour < 6:
        return "……都 %d 点了。天快亮了。" % hour
    if hour < 11:
        return "%d 点整, 上午好。" % hour
    if hour == 12:
        return "正午 12 点, 记得吃饭。"
    if hour < 18:
        return "%d 点整。" % hour
    if hour < 23:
        return "%d 点了, 晚上好。" % hour
    return "%d 点了。……夜深了。" % hour
