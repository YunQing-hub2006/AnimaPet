# -*- coding: utf-8 -*-
"""素材瘦身: 把角色卡图片降采样 + 重压缩, 砍掉"存得比用得大"的浪费。

背景
----
card.ying 原素材: 229 张 720x720 动画帧(154MB) + 7 张 2048x2048 表情图(36MB),
而桌宠实际显示尺寸 PET_SIZES 只有 180/240/320 —— 存了 2~6 倍于需要的像素。

策略
----
只降采样 + 重编码, **不动帧数、不动文件名、不动 PNG 格式**,
因此动画时序、manifest 引用、加载器逻辑全部无需改动。

目标边长 512 = 最大显示尺寸 320 的 1.6 倍, 留足高分屏(150% 缩放 -> 480 设备像素)
的清晰度余量; 再往下压会在大尺寸 + 高 DPI 下肉眼可见发虚。

用法
----
    python tools/optimize_assets.py                 # 预览(不写盘)
    python tools/optimize_assets.py --apply         # 真正执行
    python tools/optimize_assets.py --max-edge 448  # 自定义目标边长

安全性: 先写同目录临时文件再原子替换, 中途失败不会留下半张坏图。
原图已纳入 git 跟踪, 可随时 `git checkout -- mods/` 还原。
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"

DEFAULT_MAX_EDGE = 512
#: 只处理这些目录角色: 动画帧序列 / 表情静态图(mods/<卡id>/ 下)
ANIM_FRAMES_GLOB = "*/anims/*/frames/*.png"
EMOTE_GLOB = "*/images/*.png"


def _reencode(src: Path, max_edge: int, apply: bool):
    """返回 (原大小, 新大小, 原尺寸, 新尺寸); apply=False 时新大小为估算值(不落盘)。"""
    orig_bytes = src.stat().st_size
    with Image.open(src) as im:
        im.load()
        src_size = im.size
        if max(src_size) <= max_edge:
            # 已经够小: 只做无损重压缩, 不放大
            out = im.copy()
        else:
            out = im.copy()
            out.thumbnail((max_edge, max_edge), Image.LANCZOS)

        if apply:
            fd, tmp = tempfile.mkstemp(dir=str(src.parent), suffix=".tmp.png")
            os.close(fd)
            try:
                # optimize + compress_level=9: zlib 穷尽搜索, CPU 换体积
                out.save(tmp, "PNG", optimize=True, compress_level=9)
                new_bytes = os.path.getsize(tmp)
                if new_bytes < orig_bytes:
                    os.replace(tmp, src)
                else:
                    os.unlink(tmp)
                    new_bytes = orig_bytes
            except Exception:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        else:
            # 预览: 编码进内存量真实体积, 不落盘
            import io
            buf = io.BytesIO()
            out.save(buf, "PNG", optimize=True, compress_level=9)
            new_bytes = min(buf.tell(), orig_bytes)

        return orig_bytes, new_bytes, src_size, out.size


def collect(globs):
    files = []
    for g in globs:
        files.extend(sorted(MODS.glob(g)))
    return files


def main():
    ap = argparse.ArgumentParser(description="角色卡图片瘦身")
    ap.add_argument("--apply", action="store_true", help="真正写盘(默认只预览)")
    ap.add_argument("--max-edge", type=int, default=DEFAULT_MAX_EDGE,
                    help="目标最大边长(默认 %d)" % DEFAULT_MAX_EDGE)
    args = ap.parse_args()

    files = collect([ANIM_FRAMES_GLOB, EMOTE_GLOB])
    if not files:
        print("没有找到可处理的图片")
        return 1

    print("待处理 %d 张图片, 目标边长 %d  [%s]"
          % (len(files), args.max_edge, "写盘" if args.apply else "预览"))
    print("-" * 66)

    before = after = 0
    done = 0
    for p in files:
        try:
            ob, nb, osz, nsz = _reencode(p, args.max_edge, args.apply)
        except Exception as e:
            print("  跳过(失败): %s -> %s" % (p.name, e))
            continue
        before += ob
        after += nb
        done += 1
        if done % 40 == 0 or done == len(files):
            print("  %4d/%d  %-34s %sx%s -> %sx%s  %.0fKB -> %.0fKB"
                  % (done, len(files), p.parent.name + "/" + p.name,
                     osz[0], osz[1], nsz[0], nsz[1], ob / 1024, nb / 1024))

    print("-" * 66)
    saved = before - after
    print("原始合计: %8.1f MB" % (before / 1024 / 1024))
    print("优化合计: %8.1f MB" % (after / 1024 / 1024))
    print("节省:     %8.1f MB  (%.1f%%)" % (saved / 1024 / 1024,
                                            saved / before * 100 if before else 0))
    if not args.apply:
        print("\n这是预览。加 --apply 才会真正写盘。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
