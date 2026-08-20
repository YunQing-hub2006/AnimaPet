# -*- coding: utf-8 -*-
"""顶层测试配置: Qt offscreen 平台必须在 PyQt6 首次导入前设定。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
