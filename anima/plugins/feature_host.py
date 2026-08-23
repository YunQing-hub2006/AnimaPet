# -*- coding: utf-8 -*-
"""开放式功能插件宿主: feature 模组可携带 Python 代码(plugin.py)。

约定: plugin.py 定义 ``class Feature``(沿用 YingPet-v4 契约), 宿主注入
白名单上下文 ``FeatureContext``, 插件只能使用白名单 API(事件/气泡/表情/
状态/菜单), 不能访问核心内部::

    class Feature:
        id = "feature.xxx"
        name = "显示名"
        def on_load(self, ctx): ...    # 启用时(注册菜单/监听事件)
        def on_enable(self): ...       # 开启时(可省略)
        def on_disable(self): ...      # 关闭时(可省略)

与 YingPet 的差异: Feature 实例由 ``FeatureAdapter``(内核 Plugin ABC)包裹,
``dependencies=[]`` 强制为空; 实例的 on_load 在 adapter 的 **enable** 阶段
调用(此时依赖服务全部就绪), 事件订阅经 ctx.on 由 EffectTracker 记录,
禁用/卸载时自动回滚, 菜单项由 module_manager 分组登记、卸载即清。
"""
from __future__ import annotations

import importlib.util
import os
import sys

from anima.core import Plugin
from anima.utils import log

_log = log.get("features")


class FeatureContext:
    """插件能接触到的全部能力 —— 白名单 API(YingPet FeatureContext 的等价物)。"""

    def __init__(self, adapter, manager):
        self._adapter = adapter
        self._manager = manager
        self._mod_id = adapter.mod.id

    # 事件
    def emit(self, name, payload=None):
        """发出事件(可被行为规则监听)。"""
        try:
            self._adapter.ctx.emit(name, payload)
        except Exception as e:
            _log.warning("[%s] emit %s failed: %s", self._mod_id, name, e)

    def on(self, name, fn):
        """监听事件(经内核 EffectTracker, 插件卸载自动退订)。"""
        self._adapter.ctx.on(name, fn)

    # 表现
    def say(self, text, hold_ms=0):
        """让宠物气泡说话。运行时中途卸载等异常只记日志, 绝不让插件崩溃核心。"""
        try:
            self._manager.bridge.say(str(text), hold_ms=hold_ms)
        except Exception as e:
            _log.warning("[%s] say failed: %s", self._mod_id, e)

    def emote(self, emote_id, after_ms=0):
        """让宠物做表情。"""
        try:
            self._manager.bridge.emote(str(emote_id), after_ms=after_ms)
        except Exception as e:
            _log.warning("[%s] emote failed: %s", self._mod_id, e)

    def add_menu_action(self, label, callback):
        """向右键菜单追加一项(按模组 id 分组登记, 禁用即移除)。"""
        self._manager.add_menu(self._mod_id, str(label), callback)

    # 状态(持久化到 state.json, 热重载不丢失)
    def get_state(self, key=None):
        st = self._manager.state
        return st.data if key is None else st.get(key)

    def set_state(self, key, value, save=True):
        self._manager.state.change(key, value, save=save)

    def log(self, msg):
        _log.info("[%s] %s", self._mod_id, msg)

    def task(self, coro):
        """把协程调度到内核循环(跨线程安全; 经 module_manager.fire, 单线程测试回退 Task)。"""
        return self._manager.fire(coro)

    def run_on_ui(self, fn, *args, **kwargs):
        """把函数投递到 Qt 主线程执行(QWidget 只能在主线程创建/访问)。"""
        return self._manager.bridge.run_on_ui(fn, *args, **kwargs)

    def use(self, name, default=None):
        """按服务名获取官方服务(如 bridge/character_manager)。第三方模组请慎用。"""
        return self._adapter.ctx.use(name, default)

    # ------------------------------------------------------------------
    # 官方高级接口(素材管理器等官方模组使用; 第三方模组请慎用)
    # ------------------------------------------------------------------
    @property
    def registry(self):
        """模组注册表(只读使用)。"""
        return self._manager.registry

    @property
    def config(self):
        """全局配置 dict。改完记得调 save_config()。"""
        return self._manager.config.data

    def save_config(self):
        self._manager.config.save()

    def reload(self):
        """热重载全部模组(增删改模组文件后调用)。"""
        self._manager.rescan()

    def register_action(self, name, fn):
        """注册自定义行为动作: fn(value, ctx, full_action)。"""
        self._manager.actions.register(name, fn)

    @property
    def data(self):
        """跨热重载的插件私有数据容器(存窗口引用等)。"""
        return self._manager.feature_data(self._mod_id)

    @property
    def pet(self):
        """宠物窗口(QWidget)。用途限于: 作对话框 parent、读取几何位置贴窗。
        不要调用其内部方法 —— 表现请用 say/emote, 扩展能力请走动作注册表。"""
        return self._manager.bridge.window

    def open_path(self, path):
        """用系统默认方式打开文件/文件夹。"""
        try:
            os.startfile(str(path))
        except Exception as e:
            _log.warning("open_path %s: %s", path, e)


def load_feature_instance(mod):
    """加载插件实例(不调用 on_load, 只导入模块并实例化)。失败返回 None。

    B6: 模块同时注册进 sys.modules(键名 mods_<id>, 点号转下划线),
    测试/调试可以直接 import 插件模块。
    """
    path = os.path.join(mod.dir, mod.main)
    if not os.path.isfile(path):
        _log.warning("feature %s: 缺少 %s", mod.id, mod.main)
        return None
    spec = None
    try:
        spec = importlib.util.spec_from_file_location(
            "mods_" + mod.id.replace(".", "_"), path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, "Feature", None)
        if cls is None:
            _log.warning("feature %s: %s 里没有 Feature 类", mod.id, mod.main)
            return None
        inst = cls()
        _log.info("feature loaded: %s", mod.id)
        return inst
    except Exception as e:
        if spec is not None:
            sys.modules.pop(spec.name, None)
        _log.warning("feature %s 加载失败: %s", mod.id, e)
        return None


class FeatureAdapter(Plugin):
    """把 YingPet Feature 实例包成内核插件: 生命周期映射到 FeatureContext 回调。

    ``dependencies`` 强制为空(HANDOVER §四.2): 依赖服务在 enable 阶段通过
    module_manager 的白名单取用, 不做内核级依赖声明。
    """

    def __init__(self, mod, instance, manager):
        super().__init__()
        self.mod = mod
        self.instance = instance
        self._manager = manager
        self._ctx = None
        self._loaded = False

    # 内核要求插件 id 唯一且非空 —— 用模组 id
    @property
    def name(self) -> str:  # type: ignore[override]
        return self.mod.id

    @property
    def dependencies(self) -> list[str]:  # type: ignore[override]
        return []

    async def load(self, ctx) -> None:
        self._ctx = ctx

    @property
    def ctx(self):
        """插件内核 Context(FeatureContext 白名单内部用)。"""
        return self._ctx

    async def enable(self) -> None:
        if self.instance is None:
            return
        fctx = FeatureContext(self, self._manager)
        try:
            if not self._loaded and hasattr(self.instance, "on_load"):
                self.instance.on_load(fctx)
                self._loaded = True
            if hasattr(self.instance, "on_enable"):
                self.instance.on_enable()
        except Exception as e:
            _log.warning("feature %s enable 失败: %s", self.mod.id, e)

    async def disable(self) -> None:
        if self.instance is None:
            return
        self._manager.before_disable(self.mod.id)
        try:
            if hasattr(self.instance, "on_disable"):
                self.instance.on_disable()
        except Exception as e:
            _log.warning("feature %s on_disable: %s", self.mod.id, e)
        self._manager.remove_menu(self.mod.id)

    async def unload(self) -> None:
        self._loaded = False
