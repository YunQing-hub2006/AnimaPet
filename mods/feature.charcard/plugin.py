# -*- coding: utf-8 -*-
"""角色卡管理器 —— 内置功能模组(方案 A)。

入口/生命周期交给 module_manager 管理(启用/禁用/删除/热重载),
真正的 6 页签 GUI 在 anima/window/dialogs/charcard/(共享库)。
"""


class _ConfigFacade:
    """config 接口: 兼容点路径 set/get + save。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self._data = ctx.config

    @property
    def data(self):
        return self._data

    def get(self, key, default=None):
        if "." in key:
            node = self._data
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node
        return self._data.get(key, default)

    def set(self, key, value):
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def save(self):
        self._ctx.save_config()


class _HostFacade:
    """把 FeatureContext 包装成 CardManagerDialog 期望的 mm 接口。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self.registry = ctx.registry
        self.config = _ConfigFacade(ctx)

    def rescan(self):
        return self._ctx.reload()


class Feature:
    id = "feature.charcard"
    name = "角色卡管理器"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("角色卡管理器…", self._open)

    def _open(self):
        try:
            from anima.window.dialogs.charcard.dialog import CardManagerDialog
            dlg = CardManagerDialog(_HostFacade(self.ctx), self.ctx.pet)
            dlg.exec()
        except Exception as e:
            self.ctx.log("open charcard failed: %s" % e)

    def on_disable(self):
        pass