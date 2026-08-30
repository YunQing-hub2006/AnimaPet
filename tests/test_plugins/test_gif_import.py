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
    # 重名自动加序号
    mid2, d2 = common.import_gif(gif_file)
    assert mid2 == "anim.dance_2" and d2 != d


def test_import_gif_to_card(gif_file, tmp_path):
    card_dir = str(tmp_path / "card.x")
    os.makedirs(card_dir)
    short = assets.import_gif_to_card(card_dir, gif_file)
    assert short == "dance"
    assert os.path.isfile(os.path.join(
        card_dir, "anims", "dance", "frames", "frame_0000.png"))
    # 再导一次: 短名去重
    short2 = assets.import_gif_to_card(card_dir, gif_file)
    assert short2 == "dance_2"
