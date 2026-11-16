# -*- coding: utf-8 -*-
"""顶层测试配置: Qt offscreen 平台必须在 PyQt6 首次导入前设定。"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _drain_frame_prefetch():
    """每个用例结束后等在途解帧线程收手。

    这些线程在用 Qt 的图像 API(QImageReader); 若它们跨过 QApplication 析构的
    时点, 会直接 access violation(整包测试退出时实测崩过)。
    这里只 drain、不置退出标志, 所以后续用例的预解码照常可用。
    """
    yield
    from anima.mods import loader

    loader.drain_prefetch()
