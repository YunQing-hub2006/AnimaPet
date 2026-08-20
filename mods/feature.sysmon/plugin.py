# -*- coding: utf-8 -*-
"""系统监控: 菜单『系统状态』气泡播报 CPU / 内存占用。自 YingPet-v4 平移。

- 纯标准库: ctypes 调 kernel32 的 GetSystemTimes / GlobalMemoryStatusEx
- 读不到(非 Windows / 权限问题)时降级为提示, 绝不崩溃
- 采样在子线程做(QThread), 不卡 UI
"""
import ctypes
import ctypes.wintypes as wt
import os
import time
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from anima.utils import log

_log = log.get("feature.sysmon")

_IS_WIN = os.name == "nt"


class _SamplingThread(QThread):
    """CPU 采样需要两次 GetSystemTimes 间隔, 放子线程免得卡界面。"""
    done = pyqtSignal(dict)

    def run(self):
        try:
            self.done.emit(sample_system())
        except Exception as e:
            _log.warning("sysmon sample: %s\n%s", e, traceback.format_exc())
            self.done.emit({"ok": False, "error": str(e)})


def _system_times():
    """返回 (idle, total) 累计时间(秒)。"""
    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]

    idle, kern, user = FILETIME(), FILETIME(), FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        raise OSError("GetSystemTimes 失败")

    def sec(ft):
        return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
    return sec(idle), sec(idle) + sec(kern) + sec(user)


def _memory():
    """返回 (内存占用%, 总GB)。"""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "ullTotalPageFile", "ullAvailPageFile",
                "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        raise OSError("GlobalMemoryStatusEx 失败")
    return st.dwMemoryLoad, st.ullTotalPhys / (1024 ** 3)


def sample_system(interval=0.3):
    """一次完整采样: {ok, cpu, mem, total_gb}。独立纯函数便于单测。"""
    if not _IS_WIN:
        return {"ok": False, "error": "仅支持 Windows"}
    i1, t1 = _system_times()
    time.sleep(interval)
    i2, t2 = _system_times()
    total_d, idle_d = t2 - t1, i2 - i1
    cpu = 0.0 if total_d <= 0 else round((1.0 - idle_d / total_d) * 100, 1)
    mem, total_gb = _memory()
    return {"ok": True, "cpu": cpu, "mem": mem, "total_gb": round(total_gb, 1)}


def sysmon_text(r):
    """结果 dict → 台词。独立纯函数便于单测。"""
    if not r.get("ok"):
        return "……读不到系统信息。(仅支持 Windows)"
    text = "CPU %s%%, 内存 %s%% (共 %s GB)。" % (
        r.get("cpu", "?"), r.get("mem", "?"), r.get("total_gb", "?"))
    mem = r.get("mem") or 0
    cpu = r.get("cpu") or 0
    if mem >= 90 or cpu >= 90:
        text += " 快撑不住了, 关几个程序吧。"
    elif mem >= 75 or cpu >= 75:
        text += " 有点吃力了。"
    return text


class Feature:
    id = "feature.sysmon"
    name = "系统监控"

    def on_load(self, ctx):
        self.ctx = ctx
        self._worker = None
        self._alive = True   # B2: 存活标记, 迟到的线程回调据此丢弃
        orphans = ctx.data.setdefault("orphan_workers", [])
        for w in list(orphans):
            if not w.isRunning():
                orphans.remove(w)
        ctx.add_menu_action("系统状态", self._query)
        ctx.log("已加载")

    def on_enable(self):
        self._alive = True

    def on_disable(self):
        # B2: 先断开 done 信号再 wait, 杜绝"卸载后回调已卸载 ctx"; 宿主已先发 feature.disabling
        self._alive = False
        w = getattr(self, "_worker", None)
        if w is not None:
            try:
                w.done.disconnect(self._on_done)
            except (TypeError, RuntimeError):
                pass
            if w.isRunning():
                w.wait(3000)   # 采样最长几秒, 等子线程收尾
            if w.isRunning():
                self.ctx.data.setdefault("orphan_workers", []).append(w)
                w.finished.connect(w.deleteLater)
            self._worker = None

    def _query(self):
        if self._worker is not None and self._worker.isRunning():
            self.ctx.say("在看了, 别急。……")
            return
        self._worker = _SamplingThread()
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, r):
        if not getattr(self, "_alive", True):
            return   # 插件已禁用/卸载, 丢弃迟到的回调
        self._worker = None
        self.ctx.say(sysmon_text(r))
        if r.get("ok"):
            self.ctx.emit("feature.sysmon.updated", {
                "cpu": r.get("cpu"), "mem": r.get("mem")})
