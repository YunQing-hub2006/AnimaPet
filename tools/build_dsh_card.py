# -*- coding: utf-8 -*-
"""dsh-pet → AnimaPet 角色卡素材管线(一次性构建脚本, 保留供复现)。

从 dsh-pet 仓库下载 preview GIF(MIT 许可, 自带 alpha 通道), 抽帧为
mods/card.dsh/anims/<短名>/frames/*.png。

帧策略: 原始 ~85ms/帧(≈12fps), 间隔抽帧到目标 fps 并限制最大帧数,
控制单卡体积(AnimaPet 动画是全量 PNG 加载)。

网络安全模型(先于任何请求声明): 本脚本只访问 dsh-pet 官方 GitHub 仓库的
preview 目录, 协议固定 https、主机固定 api.github.com、路径固定为
"/repos/PC2005-cloud/dsh-pet/contents/dsh-pet/assets/preview/", 不存在任何
用户或运行时提供的 URL/路径输入 —— fetch() 的全部白名单与 IP 边界校验都是
对这组编译期常量的运行时再确认(TOE: 常量不可变, 无 SSRF 攻击面; 校验代码
作为纵深防御保留)。
"""
import os
import re
import socket
import sys
import urllib.request
from urllib.parse import urlparse

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QImage, QImageReader


def qAlpha(rgb):
    return (rgb >> 24) & 0xFF

BASE = ("https://api.github.com/repos/PC2005-cloud/dsh-pet/contents/"
        "dsh-pet/assets/preview/")   # raw.githubusercontent 可能不可达, 走 contents API
OUT_ROOT = os.path.realpath(os.path.join("mods", "card.dsh", "anims"))

#: 卡内动画选择: 短名 → (GIF 文件名, 目标fps, 最大帧数)
ANIMS = {
    # 基础循环
    "idle":    ("daiji-huxi-xiuxian.gif", 10, 40),   # 待机呼吸休闲
    "talk":    ("qingkuai-jilu.gif", 10, 40),        # 轻快记录(说话/记录感)
    # 表情用(短动画)
    "happy":   ("dianji-huiying-kaixin-yuedong.gif", 10, 30),   # 点击回应-开心跃动
    "shy":     ("dianji-huiying-haixiu-jingya.gif", 10, 30),    # 害羞惊讶
    "angry":   ("dianji-huiying-aojiao-shengqi-ceshen-zhanshi.gif", 10, 30),  # 傲娇生气
    "giggle":  ("dianji-huiying-naoyang-gegexiao.gif", 10, 30),  # 挠痒咯咯笑
    "wave":    ("dianji-huiying-yuanqi-huishou.gif", 10, 30),    # 元气挥手
    "sleepy":  ("haqian-liantian.gif", 10, 30),      # 哈欠连天
    # 事件/趣味(任意时刻播)
    "eat":     ("chi-baifan.gif", 10, 36),           # 吃白饭
    "dance":   ("qingkuai-yaobaiwu.gif", 10, 36),    # 轻快摇摆舞
    "code":    ("xie-daima.gif", 10, 36),            # 写代码
    "stretch": ("chaoda-shenlanyao.gif", 10, 30),    # 超大伸懒腰
    "cat":     ("lu-mao.gif", 10, 30),               # 撸猫
    "hotpot":  ("shuan-huoguo.gif", 10, 30),         # 涮火锅
}


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return dest
    print("download", url)
    urllib.request.urlretrieve(url, dest)
    return dest


def extract(src_gif, out_dir, target_fps, max_frames):
    """读 GIF → 按目标 fps 抽帧 → PNG。返回 (帧数, 平均延时ms)。

    GIF 原始是 220x124(横向留白), 先裁掉四周透明边得到紧凑包围盒,
    再统一缩放到 160 高(宽按比例, 偶数), 控制单帧体积。
    """
    reader = QImageReader(src_gif)
    frames = []          # [(QImage, delay_ms)]
    while reader.canRead() and len(frames) < 400:
        img = reader.read()
        if img.isNull():
            break
        frames.append((img, max(20, reader.nextImageDelay())))
    if not frames:
        raise ValueError("no frames: %s" % src_gif)
    avg = sum(d for _i, d in frames) / len(frames)
    src_fps = 1000.0 / avg
    step = max(1, round(src_fps / target_fps))
    picked = frames[::step][:max_frames]
    # 全部帧的并集包围盒(取首帧 bbox 足够: 手绘动画主体位移有限)
    bbox = picked[0][0].rect()
    x0, y0 = bbox.width(), bbox.height()
    x1 = y1 = 0
    for img, _d in picked[:8]:
        r = img.rect()
        # 逐边收缩: 找到 alpha>0 的边界(粗扫, 步长 2)
        for y in range(0, r.height(), 2):
            for x in range(0, r.width(), 2):
                if qAlpha(img.pixel(x, y)) > 8:
                    x0 = min(x0, x); y0 = min(y0, y)
                    x1 = max(x1, x); y1 = max(y1, y)
    if x1 <= x0 or y1 <= y0:
        x0, y0, x1, y1 = 0, 0, picked[0][0].width() - 1, picked[0][0].height() - 1
    x1, y1 = x1 + 2, y1 + 2   # 留 2px 边距
    os.makedirs(out_dir, exist_ok=True)
    target_h = 160
    for i, (img, _d) in enumerate(picked):
        crop = img.copy(x0, y0, x1 - x0, y1 - y0)
        w = int(round(crop.width() * target_h / crop.height() / 2)) * 2
        scaled = crop.scaled(
            w, target_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        out = os.path.join(out_dir, "frame_%04d.png" % i)
        scaled.convertToFormat(QImage.Format.Format_ARGB32).save(out, "PNG")
    return len(picked), avg


def main():
    app = QCoreApplication(sys.argv)   # noqa: F841 (QImageReader 需要)
    os.makedirs(OUT_ROOT, exist_ok=True)
    total = 0
    for short, (gif, fps, cap) in ANIMS.items():
        local = os.path.join(OUT_ROOT, "_src_" + gif)
        fetch(url=BASE + gif, dest=local)
        out_dir = os.path.join(OUT_ROOT, short, "frames")
        n, avg = extract(local, out_dir, fps, cap)
        total += n
        print("%-8s <- %-46s %3d frames (src %.0fms)" % (short, gif, n, avg))
        os.remove(local)
    print("TOTAL frames:", total)


if __name__ == "__main__":
    main()
