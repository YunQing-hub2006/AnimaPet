# -*- coding: utf-8 -*-
"""窗口对话框共用工具: 内核等待 / 统一样式 / PNG 序列帧与 GIF 导入。

此前 wait_fire 在 modmanager 与 charcard 各有一份、PNG 导入逻辑在
modmanager 与 charcard/assets 各有一份 —— 全部收拢到这里, 单一出处。
GIF 导入用 QImageReader 解帧(零新依赖, Qt 自带 GIF 解码)。
"""
import asyncio
import os
import re
import shutil

from PyQt6.QtGui import QImageReader

from anima.utils import jsonio, log, paths, theme

_log = log.get("window.dialogs.common")

#: 单个 GIF 最多解出的帧数(防超大 GIF 拖垮磁盘/扫描)
GIF_MAX_FRAMES = 600


# ----------------------------------------------------------------------
# 等待内核调度结果
# ----------------------------------------------------------------------

def wait_fire(fut, timeout=10):
    """等待 fire() 的调度结果。

    fire 有两种返回: 跨线程(生产, Qt 线程) → concurrent Future(带超时);
    单线程测试 → asyncio.Task(``result()`` 不接受超时参数, 未完成抛
    InvalidStateError, 由外层事件循环推动, 调用方 await 后再断言)。
    """
    if fut is None:   # 内核线程已同步执行
        return
    if isinstance(fut, asyncio.Task):
        try:
            fut.result()
        except asyncio.InvalidStateError:
            pass
        except Exception:
            raise
    else:
        fut.result(timeout)


def wait_rescan(fut):
    """等待 rescan 完成(上限 10s); 失败只记日志, 不打断对话框。"""
    try:
        wait_fire(fut, timeout=10)
    except Exception as e:
        _log.warning("rescan: %s", e)


# ----------------------------------------------------------------------
# 统一样式
# ----------------------------------------------------------------------

def _skin_theme_from(dlg):
    """从对话框持有的总管理器读当前皮肤主题; 拿不到就返回空(回落默认主题)。"""
    host = getattr(dlg, "mm", None) or getattr(dlg, "host", None)
    registry = getattr(host, "registry", None)
    config = getattr(host, "config", None)
    if registry is None or config is None:
        return {}
    try:
        skin = registry.ui(config.get("mods.ui", ""))
    except Exception as e:          # 皮肤模组损坏不该挡住对话框打开
        _log.warning("dialog skin lookup failed: %s", e)
        return {}
    return getattr(skin, "theme", None) or {}


def apply_dialog_style(dlg, theme_dict=None):
    """给对话框套当前皮肤主题(替代各处自带的 WHITE_STYLE)。

    ``theme_dict`` 省略时自动按 ``mods.ui`` 取当前皮肤 —— 早先这里写死
    ``merge_theme({})`` 只拿默认主题, 于是换了浅色皮肤后主窗口/气泡/聊天面板
    都跟着变浅, 四个对话框还是深紫, 跟主题系统"全局一致"的契约对不上。

    对话框是临时窗口, 构造时取一次就够; 换皮肤后重开即生效(主窗口是常驻的,
    由 PetWindow._apply_skin 走热重载)。
    """
    if theme_dict is None:
        theme_dict = _skin_theme_from(dlg)
    dlg.setStyleSheet(theme.dialog_qss(theme.merge_theme(theme_dict or {})))


# ----------------------------------------------------------------------
# PNG 序列帧导入(公共素材库)
# ----------------------------------------------------------------------

def _pngs(src):
    return sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))


def import_anim_folder(src):
    """把装满 PNG 的文件夹导入为公共素材库 anim.* 模组, 返回 (new_id, mod_dir)。"""
    files = _pngs(src)
    if not files:
        raise ValueError("所选文件夹里没有 PNG 文件。")
    base = re.sub(r"[^\w一-鿿-]+", "_", os.path.basename(src)).strip("_") or "anim"
    mid, d = _alloc_library_anim_dir(base)
    frames_dir = os.path.join(d, "frames")
    for f in files:
        shutil.copy2(os.path.join(src, f), os.path.join(frames_dir, f))
    jsonio.save(os.path.join(d, "manifest.json"), {
        "id": mid, "type": "anim", "version": "1.0.0",
        "name": os.path.basename(d)[len("anim."):], "fps": 12, "frames_dir": "frames",
        "description": "导入的动画(公共素材库)",
    })
    return mid, d


# ----------------------------------------------------------------------
# GIF 导入(解帧为 PNG 序列)
# ----------------------------------------------------------------------

def extract_gif_frames(src_gif, frames_dir):
    """把 GIF 逐帧导出为 frames_dir 下的 PNG 序列, 返回 (帧数, fps)。

    用 QImageReader 解码(Qt 自带 GIF 支持, 不引第三方依赖);
    帧延时普遍偏小的按 20ms 兜底, fps 由平均延时折算并夹在 1~30。
    """
    reader = QImageReader(src_gif)
    os.makedirs(frames_dir, exist_ok=True)
    delays = []
    count = 0
    while reader.canRead() and count < GIF_MAX_FRAMES:
        img = reader.read()
        if img.isNull():
            break
        if not img.save(os.path.join(frames_dir, "frame_%04d.png" % count), "PNG"):
            raise ValueError("第 %d 帧写出失败(磁盘或路径问题)。" % (count + 1))
        delays.append(max(20, reader.nextImageDelay()))
        count += 1
    if count == 0:
        raise ValueError("这个 GIF 读不出任何帧(文件可能已损坏)。")
    if reader.canRead() and count >= GIF_MAX_FRAMES:
        _log.warning("gif %s 超过 %d 帧, 已截断", src_gif, GIF_MAX_FRAMES)
    fps = min(30, max(1, round(1000.0 / (sum(delays) / len(delays)))))
    return count, fps


def import_gif(src_gif):
    """把 GIF 导入为公共素材库 anim.* 模组(自动解帧), 返回 (new_id, mod_dir)。

    解帧或写 manifest 失败就把刚建好的目录整个删掉。早先失败时目录留在盘上,
    而 loader 扫到没有 manifest 的目录只是 continue 跳过(不报错也不显示),
    于是每重试一次就多一个垃圾目录, 重名还会一路跳到 _2/_3。
    """
    stem = os.path.splitext(os.path.basename(src_gif))[0]
    base = re.sub(r"[^\w一-鿿-]+", "_", stem).strip("_") or "anim"
    mid, d = _alloc_library_anim_dir(base)
    try:
        n, fps = extract_gif_frames(src_gif, os.path.join(d, "frames"))
        jsonio.save(os.path.join(d, "manifest.json"), {
            "id": mid, "type": "anim", "version": "1.0.0",
            "name": os.path.basename(d)[len("anim."):], "fps": fps, "frames_dir": "frames",
            "description": "由 GIF 导入的动画(%d 帧, 公共素材库)" % n,
        })
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return mid, d


def _alloc_library_anim_dir(base):
    """在素材库分配 anim.<名> 目录(重名自动加序号), 返回 (mid, mod_dir)。

    只建 frames/ 目录, 不写 manifest —— 由调用方按导入来源补齐元数据。
    """
    name = base
    i = 1
    while os.path.isdir(os.path.join(paths.MODS_DIR, "anim." + name)):
        name = "%s_%d" % (base, i)   # 先改名再自增, 否则重名会跳过 _1 直接叫 _2
        i += 1
    mid = "anim." + name
    d = os.path.join(paths.MODS_DIR, mid)
    os.makedirs(os.path.join(d, "frames"), exist_ok=True)
    return mid, d
