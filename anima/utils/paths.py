# -*- coding: utf-8 -*-
"""路径解析: 兼容源码运行与 PyInstaller 打包(frozen)。

运行时数据(config/state/log)统一落 ``data/`` 目录, 与源码、模组分离。
"""
import os
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)      # PyInstaller: exe 旁边
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODS_DIR = os.path.join(BASE_DIR, "mods")
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
CHAT_HISTORY_DIR = os.path.join(DATA_DIR, "chat_history")
LOG_PATH = os.path.join(DATA_DIR, "pet.log")
