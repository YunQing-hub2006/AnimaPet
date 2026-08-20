# -*- coding: utf-8 -*-
"""天气插件: 免费、无需 Key。自 YingPet-v4 平移, 契约不变(仅 import 改 anima)。

数据源(依次兜底):
1. wttr.in ?format=j1  —— 一个请求同时拿到 IP 定位 + 天气
2. ip-api.com 定位 + Open-Meteo 预报 —— 两个请求

约定:
- 请求放 QThread, 绝不卡 UI; requests 延迟导入(无网络模块零成本)
- 结果通过 ctx.emit("feature.weather.updated", {...}) 广播, 行为规则可监听联动
- 全程失败只说一句"网络不好", 静默降级
"""
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from anima.utils import log

_log = log.get("feature.weather")

# Open-Meteo WMO 天气代码 → 中文描述
WMO_DESC = {
    0: "晴", 1: "基本晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹",
}


class _Worker(QThread):
    done = pyqtSignal(dict)   # {"ok": bool, ...}

    def run(self):
        try:
            self.done.emit(fetch_weather())
        except Exception as e:
            _log.warning("weather worker: %s\n%s", e, traceback.format_exc())
            self.done.emit({"ok": False, "error": str(e)})


def fetch_weather():
    """主备两个免费源。返回 {ok, city, temp, desc} 或 {ok: False, error}。"""
    try:
        data = _get_json("https://wttr.in/?format=j1", timeout=8)
        r = parse_wttr(data)
        if r.get("ok"):
            return r
    except Exception as e:
        _log.info("wttr.in 失败, 改用 Open-Meteo: %s", e)
    try:
        geo = _get_json("http://ip-api.com/json/", timeout=6)
        lat, lon = float(geo["lat"]), float(geo["lon"])
        fc = _get_json(
            "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
            "&current_weather=true&timezone=auto" % (lat, lon), timeout=8)
        return parse_open_meteo(geo, fc)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_json(url, timeout=8):
    import requests
    resp = requests.get(url, timeout=timeout,
                        headers={"User-Agent": "AnimaPet desktop pet"})
    resp.raise_for_status()
    return resp.json()


def parse_wttr(data):
    """wttr.in j1 → {ok, city, temp, desc}。独立纯函数便于单测。"""
    try:
        cur = data["current_condition"][0]
        city = data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", "")
        temp = float(cur["temp_C"])
        desc = str(cur.get("lang_zh", [{}])[0].get("value", "")
                   or cur.get("weatherDesc", [{}])[0].get("value", "天气"))
        return {"ok": True, "city": str(city), "temp": temp, "desc": desc}
    except (KeyError, IndexError, TypeError, ValueError) as e:
        return {"ok": False, "error": "wttr 数据格式异常: %s" % e}


def parse_open_meteo(geo, forecast):
    """ip-api 定位 + Open-Meteo current_weather → {ok, city, temp, desc}。"""
    try:
        cur = forecast["current_weather"]
        code = int(cur["weathercode"])
        return {
            "ok": True,
            "city": str(geo.get("city", "") or geo.get("regionName", "") or ""),
            "temp": float(cur["temperature"]),
            "desc": WMO_DESC.get(code, "天气代码 %d" % code),
        }
    except (KeyError, TypeError, ValueError) as e:
        return {"ok": False, "error": "open-meteo 数据格式异常: %s" % e}


def weather_text(r):
    """把结果 dict 转成角色台词。独立纯函数便于单测。"""
    if not r.get("ok"):
        return "……网络不太好, 查不到天气。"
    temp = r["temp"]
    where = ("%s " % r["city"]) if r.get("city") else ""
    hint = ""
    if temp >= 33:
        hint = " 很热, 小心中暑。"
    elif temp >= 28:
        hint = " 有点热。"
    elif temp <= 0:
        hint = " 结冰了, 多穿点。"
    elif temp <= 10:
        hint = " 偏冷, 注意保暖。"
    rain = any(k in str(r.get("desc", "")) for k in ("雨", "雪"))
    if rain:
        hint += " 带伞。"
    return "现在 %s%s℃, %s。%s" % (where, int(temp), r.get("desc", ""), hint.strip())


class Feature:
    id = "feature.weather"
    name = "天气"

    def on_load(self, ctx):
        self.ctx = ctx
        self._worker = None
        self._alive = True   # B2: 存活标记, 迟到的线程回调据此丢弃
        # 清理上次卸载时未结束的孤儿线程引用(此时若已结束可安全移除)
        orphans = ctx.data.setdefault("orphan_workers", [])
        for w in list(orphans):
            if not w.isRunning():
                orphans.remove(w)
        ctx.add_menu_action("查天气", self._query)
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
                w.wait(3000)   # 等子线程收尾, 最多 3 秒
            if w.isRunning():
                # 请求最长 20s: 3s 没结束就把引用移交给宿主数据容器 + 延迟删除,
                # 绝不能让 QThread 在运行中被析构(会崩)
                self.ctx.data.setdefault("orphan_workers", []).append(w)
                w.finished.connect(w.deleteLater)
            self._worker = None

    def _query(self):
        if self._worker is not None and self._worker.isRunning():
            self.ctx.say("在查了, 别急。……")
            return
        self.ctx.say("我看一眼天。……")
        self._worker = _Worker()
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, r):
        if not getattr(self, "_alive", True):
            return   # 插件已禁用/卸载, 丢弃迟到的回调
        self._worker = None
        self.ctx.say(weather_text(r))
        if r.get("ok"):
            # 广播给行为规则: 例如"下雨时让角色提醒带伞"可写成一条规则
            self.ctx.emit("feature.weather.updated", {
                "city": r.get("city", ""), "temp": r.get("temp"),
                "desc": r.get("desc", ""),
            })
