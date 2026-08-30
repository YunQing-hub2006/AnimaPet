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

def apply_dialog_style(dlg):
    """给对话框套全局统一暗色主题(替代各处自带的 WHITE_STYLE)。"""
    dlg.setStyleSheet(theme.dialog_qss(theme.merge_theme({})))


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
    """把 GIF 导入为公共素材库 anim.* 模组(自动解帧), 返回 (new_id, mod_dir)。"""
    stem = os.path.splitext(os.path.basename(src_gif))[0]
    base = re.sub(r"[^\w一-鿿-]+", "_", stem).strip("_") or "anim"
    mid, d = _alloc_library_anim_dir(base)
    frames_dir = os.path.join(d, "frames")
    n, fps = extract_gif_frames(src_gif, frames_dir)
    jsonio.save(os.path.join(d, "manifest.json"), {
        "id": mid, "type": "anim", "version": "1.0.0",
        "name": os.path.basename(d)[len("anim."):], "fps": fps, "frames_dir": "frames",
        "description": "由 GIF 导入的动画(%d 帧, 公共素材库)" % n,
    })
    return mid, d


def _alloc_library_anim_dir(base):
    """在素材库分配 anim.<名> 目录(重名自动加序号), 返回 (mid, mod_dir)。

    只建 frames/ 目录, 不写 manifest —— 由调用方按导入来源补齐元数据。
    """
    name = base
    i = 1
    while os.path.isdir(os.path.join(paths.MODS_DIR, "anim." + name)):
        i += 1
        name = "%s_%d" % (base, i)
    mid = "anim." + name
    d = os.path.join(paths.MODS_DIR, mid)
    os.makedirs(os.path.join(d, "frames"), exist_ok=True)
    return mid, d
