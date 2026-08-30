# -*- coding: utf-8 -*-
"""GIF 导入测试: 解帧(QImageReader) → PNG 序列 → anim.* 模组 / 卡内动画。"""
import base64
import json
import os

import pytest
from PyQt6.QtWidgets import QApplication

from anima.utils import jsonio, paths
from anima.window.dialogs import common
from anima.window.dialogs.charcard import assets

#: 经典 1x1 GIF(单帧), 测试用最小样本
TINY_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def gif_file(tmp_path):
    p = tmp_path / "dance.gif"
    p.write_bytes(TINY_GIF)
    return str(p)


def test_extract_gif_frames_writes_png_and_fps(gif_file, tmp_path):
    frames_dir = str(tmp_path / "frames")
    n, fps = common.extract_gif_frames(gif_file, frames_dir)
    assert n == 1
    assert 1 <= fps <= 30
    pngs = sorted(os.listdir(frames_dir))
    assert pngs == ["frame_0000.png"]
    assert os.path.getsize(os.path.join(frames_dir, pngs[0])) > 0


def test_extract_gif_rejects_broken_file(tmp_path):
    bad = tmp_path / "bad.gif"
    bad.write_bytes(b"not a gif at all")
    with pytest.raises(ValueError):
        common.extract_gif_frames(str(bad), str(tmp_path / "frames"))


def test_import_gif_creates_library_mod(gif_file, tmp_path, monkeypatch):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    mid, d = common.import_gif(gif_file)
    assert mid == "anim.dance"
    mf = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    assert mf["type"] == "anim" and mf["frames_dir"] == "frames"
    assert 1 <= int(mf["fps"]) <= 30
    assert len(os.listdir(os.path.join(d, "frames"))) == 1
    # 重名自动加序号(从 _1 开始, 别跳号)
    mid2, d2 = common.import_gif(gif_file)
    assert mid2 == "anim.dance_1" and d2 != d
    mid3, _ = common.import_gif(gif_file)
    assert mid3 == "anim.dance_2"


def test_import_gif_rolls_back_dir_on_failure(tmp_path, monkeypatch):
    """解帧失败要把刚建的 anim.* 目录删掉。

    早先失败时目录留在盘上, 而 loader 扫到没 manifest 的目录只是 continue
    跳过(不报错也不显示), 于是每重试一次就多一个垃圾目录。
    """
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    bad = tmp_path / "broken.gif"
    bad.write_bytes(b"not a gif at all")
    with pytest.raises(ValueError):
        common.import_gif(str(bad))
    assert os.listdir(mods_dir) == [], "失败的导入不该留下孤儿目录"


def test_import_gif_to_card(gif_file, tmp_path):
    card_dir = str(tmp_path / "card.x")
    os.makedirs(card_dir)
    short = assets.import_gif_to_card(card_dir, gif_file)
    assert short == "dance"
    assert os.path.isfile(os.path.join(
        card_dir, "anims", "dance", "frames", "frame_0000.png"))
    # 再导一次: 短名去重(从 _1 开始)
    short2 = assets.import_gif_to_card(card_dir, gif_file)
    assert short2 == "dance_1"


def test_import_gif_to_card_rolls_back_on_failure(gif_file, tmp_path):
    """卡内导入失败别留下空动画目录(它会在动画页签显示成一套空动画)。"""
    card_dir = str(tmp_path / "card.x")
    os.makedirs(card_dir)
    bad = tmp_path / "broken.gif"
    bad.write_bytes(b"not a gif at all")
    with pytest.raises(ValueError):
        assets.import_gif_to_card(card_dir, str(bad))
    assert os.listdir(os.path.join(card_dir, "anims")) == []
