# -*- coding: utf-8 -*-
"""角色卡管理器 (自 YingPet-v4 feature.charcard 平移)。

数据源: module_manager 服务(mm)+ registry/config 服务; 保存动作统一经
anima.models.load_card 整体预检(坏数据弹错不落盘); 重扫走 mm.rescan()
(线程感知)+ 跨线程等待 —— 等待逻辑在 dialogs.common, 此处仅再导出兼容。
"""
from anima.window.dialogs.common import wait_fire, wait_rescan

__all__ = ["wait_fire", "wait_rescan"]
