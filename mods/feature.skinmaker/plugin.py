# -*- coding: utf-8 -*-
"""皮肤工坊 —— 内置功能模组(方案 A)。

入口/生命周期交给 module_manager 管理; 真正的取色/预览 GUI 在
anima/window/dialogs/skinmaker.py(共享库)。保存生成的 ui.* 皮肤与
手写皮肤完全同构, 可进模组管理统一开关/删除。
"""


class _ConfigFacade:
    """config 接口: 兼容点路径 set/get + save(与 feature.charcard 相同)。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self._data = ctx.config

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
    """把 FeatureContext 包装成 SkinMakerDialog 期望的 host 接口。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self.registry = ctx.registry
        self.config = _ConfigFacade(ctx)

    def rescan(self):
        return self._ctx.reload()


class Feature:
    id = "feature.skinmaker"
    name = "皮肤工坊"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("皮肤工坊…", self._open)

    def _open(self):
        try:
            from anima.window.dialogs.skinmaker import SkinMakerDialog
            dlg = SkinMakerDialog(_HostFacade(self.ctx), self.ctx.pet)
            dlg.exec()
        except Exception as e:
            self.ctx.log("open skinmaker failed: %s" % e)

    def on_disable(self):
        pass
