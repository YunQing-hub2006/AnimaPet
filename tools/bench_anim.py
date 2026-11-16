# -*- coding: utf-8 -*-
"""动画渲染基准(offscreen): 量化帧解码与重绘开销, 供渲染优化前后对比。

用法: .venv\\Scripts\\python tools\\bench_anim.py

测四项:
    1. 冷解码 —— 每个动画首次取帧的耗时(同步发生在 Qt 主线程上);
    2. 换角色/换尺寸 —— 清空帧缓存后 refresh_from_registry 的真实卡顿;
    3. 重绘次数 —— 100 次 tick 里 setPixmap 实际被调用几次(浪费则远大于 1);
    4. 逐帧成本 —— advance() 单次耗时与气泡打字每字耗时。
"""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from anima.mods import loader  # noqa: E402
from anima.mods.registry import Registry  # noqa: E402
from anima.window.animator import Animator  # noqa: E402

TICKS = 100

#: 进程级持有 QApplication: 若只在 main() 里局部持有, 它会先于窗口析构,
#: Qt 在解释器收尾时可能异常终止, 让脚本"跑成功却返回非 0"。
_APP = None


class _NullBus:
    def emit(self, *a, **k):
        pass

    def subscribe(self, *a, **k):
        pass


class CountingLabel(QLabel):
    """统计 setPixmap 被调用几次、其中几次画的还是上一张(纯浪费)。"""

    def __init__(self):
        super().__init__()
        self.calls = 0
        self.same = 0
        self._last = None

    def setPixmap(self, pm):
        self.calls += 1
        if self._last is not None and pm is self._last:
            self.same += 1
        self._last = pm
        super().setPixmap(pm)


def _ms(t0):
    return (time.perf_counter() - t0) * 1000


def _mean_ms(fn, n):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000


def _animator(reg, size):
    lab = CountingLabel()
    lab.resize(size, size)
    a = Animator(lab, reg, _NullBus(), size)
    a.anim_timer.stop()          # 手动驱动, 不依赖事件循环
    return a, lab


def main():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    mods, errors = loader.scan_mods()
    reg = Registry()
    reg.apply(mods)
    print("mods=%d errors=%d anims=%d" % (len(mods), len(errors), len(reg.anims)))
    if not reg.characters or not reg.anims:
        print("没有角色卡/动画, 无法基准")
        return 0

    card = reg.character("card.dsh") or next(iter(reg.characters.values()))
    idle, talk = reg.anim(card.idle_anim), reg.anim(card.talk_anim)
    print("card=%s idle=%s talk=%s" % (card.id, card.idle_anim, card.talk_anim))

    # ---- 1) 冷解码 ----
    print("\n[1] 冷解码(每个动画首次取帧, 同步阻塞 UI 线程)")
    for size in (240, 320):
        loader.clear_frame_cache()
        parts = {}
        for nm, an in (("idle", idle), ("talk", talk)):
            if an is None:
                continue
            t0 = time.perf_counter()
            frames = an.frames(size)
            parts[nm] = _ms(t0)
        total = sum(parts.values())
        print("    %dpx: %s  合计 %.1f ms" % (
            size, "  ".join("%s %.1f ms" % kv for kv in parts.items()), total))
    groups, byts = loader.cache_stats()
    print("    缓存: %d 组 / %.1f MiB" % (groups, byts / 1024 / 1024))

    # ---- 2) 换角色/换尺寸的真实卡顿 ----
    print("\n[2] refresh_from_registry —— 换角色卡/换尺寸")
    print("    同步部分应只剩首帧解码; 整组由后台补齐(下面等它到齐再复核)")
    from anima.plugins.config import ConfigService
    from anima.plugins.state import StateService
    from anima.window.pet_window import PetWindow

    cfg, st = ConfigService(), StateService()
    cfg.load()
    st.load()
    cfg.set("mods.character", card.id)
    win = PetWindow(reg, _NullBus(), cfg, st)
    for size in (240, 320):
        loader.clear_frame_cache()          # 冷启动/首次切到该尺寸
        t0 = time.perf_counter()
        win.display_size = size
        win.refresh_from_registry()
        sync_ms = _ms(t0)
        first_n = len(win.animator.idle_frames)
        ia, ta = win._current_anims()
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if loader.is_cached(ia, size) and (ta is None or loader.is_cached(ta, size)):
                break
            _APP.processEvents()            # queued signal 靠事件循环投递
            time.sleep(0.005)
        full_n = len(win.animator.idle_frames)
        print("    %dpx 冷切换: 同步 %.1f ms (先出画 %d 帧) -> 后台补齐 %d 帧"
              % (size, sync_ms, first_n, full_n))
        assert full_n > first_n, "后台帧组没有补齐!"
    t0 = time.perf_counter()
    win.refresh_from_registry()
    print("    同尺寸热切换: %.1f ms (缓存命中, 不触发后台)" % _ms(t0))

    # ---- 3) 重绘次数(TICKS 次 tick 里 setPixmap 实际调用几次) ----
    print("\n[3] 重绘次数 / %d 次 tick —— 期望: 多帧动画 == %d, 静态内容 == 1" % (TICKS, TICKS))
    if idle is not None:
        a, lab = _animator(reg, 240)
        a.set_frames(idle.frames(240), idle.frames(240))
        for _ in range(TICKS):
            a.advance()
        print("    %d 帧 idle 循环         : setPixmap=%d  其中重复=%d"
              % (len(a.idle_frames), lab.calls, lab.same))

    a, lab = _animator(reg, 240)
    a.play_frames = [QPixmap(4, 4)]
    a.mode = "anim"
    for _ in range(TICKS):
        a.advance()
    print("    单帧动画                : setPixmap=%d  其中重复=%d"
          % (lab.calls, lab.same))

    a, lab = _animator(reg, 240)
    static = [e for e in reg.emotes.values() if e.image and not e.anim]
    if static:
        a.set_frames(idle.frames(240) if idle else [], [])
        a.mode, a.current_emote = "expr", static[0].id
        for _ in range(TICKS):
            a.advance()
        print("    静态表情 %-12r: setPixmap=%d  其中重复=%d"
              % (static[0].id, lab.calls, lab.same))

    # ---- 4) 逐帧成本 ----
    print("\n[4] 逐帧成本")
    a, _lab = _animator(reg, 240)
    a.set_frames(idle.frames(240) if idle else [], talk.frames(240) if talk else [])
    print("    advance() idle : %.4f ms/帧 (定时器 80~120ms, 占空比可忽略)"
          % _mean_ms(a.advance, 400))

    b = win.bubble
    b.say("这是一句大概二十来个字的测试台词用来测量打字机开销", hold_ms=100)
    print("    气泡 _tick     : %.4f ms/字符" % _mean_ms(b._tick, 20))
    b.close()
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
