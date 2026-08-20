# -*- coding: utf-8 -*-
"""module_manager 插件: 模组总管理器(服务 + feature 适配器 + 管理入口)。

服务名 ``"module_manager"``。按 HANDOVER §四.2 已定设计实现:

- ``list_mods()/set_enabled(id,on)/import_zip(path)/export_zip(id,path)/
  delete_mod(id)/create_feature_mod(id,name)/rescan()``
- 数据模组启停 = 写 config.mods.enabled + loader.rescan(registry.apply 重建);
- feature 模组启停 = 内核 lifecycle.enable/disable(FeatureAdapter 包装,
  强制 ``dependencies=[]``); 新增 = ``load_all([适配器]) + enable``; 删除 = unload;
- zip 导入导出走 anima.mods.packer(Zip-Slip 三重拒绝、id_2 冲突改名回写
  manifest、__pycache__/.pyc 过滤、失败 rmtree 回滚);
- 功能菜单按模组 id 分组经 bridge 登记, 禁用即移除;
- 管理对话框(ModsDialog)入口登记到右键菜单"功能"。

跨线程约定: 服务方法分两层 —— async 核心方法(a_*)供内核线程/测试 await;
同步门面(fire 调度)供 Qt 线程(管理对话框)调用, 经 run_coroutine_threadsafe
投递到内核事件循环, 不阻塞 UI。
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil

from anima.core import Context, Plugin
from anima.events import EventNames
from anima.mods import packer
from anima.mods.loader import FeatureMod
from anima.utils import jsonio, log, paths
from anima.plugins import feature_host

_log = log.get("module_manager")

_FEATURE_ID_RE = re.compile(r"[A-Za-z0-9._\-]+")

#: create_feature_mod 生成的功能模组模板(FeatureContext 白名单契约演示)。
FEATURE_TEMPLATE = '''# -*- coding: utf-8 -*-
"""{name} —— AnimaPet 功能模组(模板)。

契约: 定义 class Feature; on_load 里用白名单 ctx 注册菜单/监听事件;
on_disable 里停线程/计时器。改完菜单"重新扫描"即热生效。
"""


class Feature:
    id = "{mod_id}"
    name = "{name}"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("{name}", self._hello)
        ctx.log("已加载")

    def _hello(self):
        self.ctx.say("你好, 我是功能模组 {name}。")
        self.ctx.emit("{mod_id}.clicked", {{}})
'''


class ModuleManagerService:
    """模组总管理器: 数据层 + 生命周期编排(由 ModuleManagerPlugin provide)。"""

    def __init__(self) -> None:
        self._ctx: Context | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._adapters: dict[str, feature_host.FeatureAdapter] = {}
        self._instances: dict[str, object] = {}
        self._data: dict[str, dict] = {}
        self._loading: set[str] = set()   # 防重入(多路 sync 并发时)

    # -- 装配 -------------------------------------------------------------

    def bind(self, ctx: Context, loop=None) -> None:
        """插件 load 阶段调用: 记录内核 Context 与事件循环(main.py 传入)。"""
        self._ctx = ctx
        self._loop = loop

    def fire(self, coro):
        """跨线程调度协程(不阻塞调用方)。

        内核线程(有运行循环)→ 直接 create_task; Qt 线程 → 经
        run_coroutine_threadsafe 投递到内核循环; 两者皆无 → 丢弃并记日志。
        """
        loop = self._loop
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if loop is not None and running is not loop:
            return asyncio.run_coroutine_threadsafe(coro, loop)
        if running is not None:
            return running.create_task(coro)
        _log.warning("fire %r dropped: no running loop", coro)
        coro.close()
        return None

    # -- 服务快捷访问 -----------------------------------------------------

    @property
    def config(self):
        return self._ctx.use("config")

    @property
    def state(self):
        return self._ctx.use("state")

    @property
    def registry(self):
        return self._ctx.use("mods")

    @property
    def bridge(self):
        return self._ctx.use("bridge")

    @property
    def actions(self):
        return self._ctx.use("actions")

    def open_path(self, path):
        try:
            os.startfile(str(path))
        except Exception as e:
            _log.warning("open_path %s: %s", path, e)

    # -- 查询 -------------------------------------------------------------

    def list_mods(self) -> list[dict]:
        """全部模组(含未启用)的摘要列表, 供管理面板渲染。"""
        out = []
        for m in self.registry.all_mods:
            out.append({
                "id": m.id,
                "type": m.type if hasattr(m, "type") else _mod_type(m),
                "name": getattr(m, "name", "") or m.id,
                "version": getattr(m, "version", "") or "",
                "description": getattr(m, "description", "") or "",
                "enabled": self.is_enabled(m.id),
                "feature": isinstance(m, FeatureMod),
            })
        return out

    def is_enabled(self, mod_id: str) -> bool:
        enabled = self.config.get("mods.enabled", {})
        return bool(enabled.get(str(mod_id), True))

    def _mod(self, mod_id: str):
        for m in self.registry.all_mods:
            if m.id == str(mod_id):
                return m
        return None

    # -- 开关 -------------------------------------------------------------

    async def set_enabled(self, mod_id: str, on: bool) -> None:
        """启用/禁用模组(持久化开关; feature 走内核生命周期, 数据模组重建注册表)。"""
        mod_id = str(mod_id)
        self._write_enabled(mod_id, bool(on))
        mod = self._mod(mod_id)
        if isinstance(mod, FeatureMod):
            await self._set_feature_enabled(mod, bool(on))
        else:
            self._ctx.use("loader").rescan()

    def _write_enabled(self, mod_id: str, on: bool) -> None:
        cfg = self.config
        enabled = dict(cfg.get("mods.enabled", {}) or {})
        enabled[mod_id] = on
        cfg.set("mods.enabled", enabled)
        cfg.save()

    async def _set_feature_enabled(self, mod: FeatureMod, on: bool) -> None:
        lifecycle = self._ctx.app.lifecycle
        if on:
            await self._ensure_adapter(mod)
            if lifecycle.get_state(mod.id) in ("loaded", "disabled"):
                await lifecycle.enable(mod.id)
                self._ctx.emit(EventNames.PLUGIN_ENABLED, {"plugin": mod.id})
        else:
            # 禁用 = 完整卸载(与 YingPet 对等语义): 副作用回滚、菜单移除;
            # 再启用时 _ensure_adapter 会造全新实例重新 on_load
            await self._unload_adapter(mod.id)
            self._ctx.emit(EventNames.PLUGIN_DISABLED, {"plugin": mod.id})

    async def _unload_adapter(self, mod_id: str) -> None:
        lifecycle = self._ctx.app.lifecycle
        if lifecycle.get_state(mod_id) in ("loaded", "enabled", "disabled"):
            await lifecycle.unload(mod_id)
        self._adapters.pop(mod_id, None)
        self._instances.pop(mod_id, None)
        for m in self.registry.all_mods:
            if m.id == mod_id:
                m.instance = None

    async def _ensure_adapter(self, mod: FeatureMod):
        """加载并 load_all 适配器(幂等)。实例加载失败也保留空适配器占位。"""
        if mod.id in self._adapters:
            return
        inst = feature_host.load_feature_instance(mod)
        adapter = feature_host.FeatureAdapter(mod, inst, self)
        await self._ctx.app.lifecycle.load_all([adapter])
        self._adapters[mod.id] = adapter
        if inst is not None:
            self._instances[mod.id] = inst
        mod.instance = inst

    # -- 重扫与 feature 对账 ---------------------------------------------

    def rescan(self) -> None:
        """重扫 mods/ 并广播 mods.reloaded(feature 对账由事件驱动, 见 sync_features)。"""
        self._ctx.use("loader").rescan()

    async def a_rescan(self) -> None:
        """异步版: 重扫 + 等 feature 对账完成(测试/内核线程用)。"""
        self.rescan()
        await self.sync_features()

    async def sync_features(self) -> None:
        """按当前注册表+开关表对账 feature 生命周期(幂等, 可并发调用)。"""
        if self._ctx is None or self._loading:
            return
        self._loading.add("sync")
        try:
            lifecycle = self._ctx.app.lifecycle
            enabled_map = self.config.get("mods.enabled", {}) or {}
            live = set()
            for mod in list(self.registry.all_mods):
                if not isinstance(mod, FeatureMod):
                    continue
                live.add(mod.id)
                on = bool(enabled_map.get(mod.id, True))
                if on:
                    await self._ensure_adapter(mod)
                    if lifecycle.get_state(mod.id) in ("loaded", "disabled"):
                        await lifecycle.enable(mod.id)
                elif lifecycle.get_state(mod.id) in ("loaded", "enabled", "disabled"):
                    await self._unload_adapter(mod.id)
            # 注册表里已消失的 feature: 卸载适配器、清理登记
            for mid in list(self._adapters):
                if mid not in live:
                    await self._unload_adapter(mid)
                    self._data.pop(mid, None)
        finally:
            self._loading.discard("sync")

    # -- zip 导入导出 -----------------------------------------------------

    async def import_zip(self, zip_path: str) -> tuple[str, str]:
        """导入模组包(照搬 YingPet packer 防护), 自动启用并热生效。返回 (新id, 目录)。"""
        new_id, dest = packer.import_mod_zip(str(zip_path), paths.MODS_DIR)
        self._write_enabled(new_id, True)
        await self.a_rescan()
        return new_id, dest

    def export_zip(self, mod_id: str, dest_zip: str) -> int:
        """导出模组文件夹为 zip。返回条目数; 找不到模组抛 ValueError。"""
        m = self._mod(str(mod_id))
        if m is None:
            raise ValueError("模组不存在: %s" % mod_id)
        src = getattr(m, "dir", "") or getattr(m, "owner_dir", "")
        if not src or not os.path.isdir(src):
            raise ValueError("找不到模组文件夹: %s" % mod_id)
        return packer.export_mod(src, str(dest_zip))

    # -- 删除 -------------------------------------------------------------

    async def delete_mod(self, mod_id: str) -> None:
        """删除模组: feature 先走内核卸载(禁用+回滚副作用), 再删文件夹并重扫。"""
        mod = self._mod(str(mod_id))
        if mod is None:
            raise ValueError("模组不存在: %s" % mod_id)
        if isinstance(mod, FeatureMod):
            await self._unload_adapter(mod.id)
            self._data.pop(mod.id, None)
        src = getattr(mod, "dir", "") or getattr(mod, "owner_dir", "")
        if src and os.path.isdir(src):
            shutil.rmtree(src, ignore_errors=True)
        enabled = dict(self.config.get("mods.enabled", {}) or {})
        enabled.pop(mod.id, None)
        self.config.set("mods.enabled", enabled)
        self.config.save()
        await self.a_rescan()

    # -- 新建 feature 模组 -------------------------------------------------

    async def create_feature_mod(self, mod_id: str, name: str) -> str:
        """新建一个 feature 模组模板(manifest + plugin.py), 自动启用。返回 id。"""
        mod_id = str(mod_id).strip().lower()
        if not mod_id.startswith("feature."):
            mod_id = "feature." + mod_id
        if not _FEATURE_ID_RE.fullmatch(mod_id):
            raise ValueError("模组 id 非法: %r" % mod_id)
        target = os.path.join(paths.MODS_DIR, mod_id)
        if os.path.exists(target):
            raise ValueError("模组已存在: %s" % mod_id)
        os.makedirs(target, exist_ok=True)
        jsonio.save(os.path.join(target, "manifest.json"), {
            "id": mod_id, "type": "feature", "version": "1.0.0",
            "name": str(name or mod_id),
            "description": "create_feature_mod 生成的功能模组模板",
            "main": "plugin.py",
        })
        with open(os.path.join(target, "plugin.py"), "w", encoding="utf-8") as f:
            f.write(FEATURE_TEMPLATE.format(mod_id=mod_id, name=str(name or mod_id)))
        self._write_enabled(mod_id, True)
        await self.a_rescan()
        return mod_id

    # -- 菜单 / 私有数据(供 FeatureContext) --------------------------------

    def add_menu(self, mod_id: str, label: str, callback) -> None:
        self.bridge.add_menu(str(mod_id), label, callback)

    def remove_menu(self, mod_id: str) -> None:
        self.bridge.remove_menu(str(mod_id))

    def before_disable(self, mod_id: str) -> None:
        """适配器 on_disable 前广播(FEATURE_DISABLING, 供插件挂起线程)。"""
        if self._ctx is not None:
            self._ctx.emit(EventNames.FEATURE_DISABLING, {"feature": str(mod_id)})

    def feature_data(self, mod_id: str) -> dict:
        return self._data.setdefault(str(mod_id), {})

    @property
    def instances(self) -> dict:
        return dict(self._instances)


def _mod_type(m):
    """从模组对象类型判定 type(与 YingPet 管理面板一致)。"""
    from anima.mods import loader
    for cls, t in ((loader.CharacterMod, "character"), (loader.AnimMod, "anim"),
                   (loader.EmoteDef, "emote"), (loader.IdlePack, "idle"),
                   (loader.BehaviorMod, "behavior"), (loader.FeatureMod, "feature"),
                   (loader.UiMod, "ui")):
        if isinstance(m, cls):
            return t
    return m.id.split(".")[0] if "." in m.id else "?"


class ModuleManagerPlugin(Plugin):
    """模组总管理器插件: provide 服务, 订阅 mods.reloaded 对账 feature。"""

    name = "module_manager"
    version = "1.0.0"
    dependencies = ["config", "loader", "bridge"]

    def __init__(self, service: ModuleManagerService | None = None, loop=None) -> None:
        self._svc = service if service is not None else ModuleManagerService()
        self._loop = loop
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        self._svc.bind(ctx, self._loop)
        ctx.provide("module_manager", self._svc)
        # 重扫对账: 事件 handler 同步函数, 内里用 fire 调度到内核循环
        ctx.on(EventNames.MODS_RELOADED, lambda _data: self._svc.fire(self._svc.sync_features()))

    async def enable(self) -> None:
        """入口就绪: 登记管理菜单 + 首次 feature 对账。"""
        self._svc.add_menu("module_manager", "模组管理", self._open_mods_dialog)
        await self._svc.sync_features()

    def _open_mods_dialog(self):
        """打开模组管理对话框(在 Qt 线程被菜单触发)。"""
        try:
            from anima.window.dialogs.modmanager import ModsDialog
            dlg = ModsDialog(self._svc, self._svc.bridge.window)
            dlg.exec()
        except Exception as e:
            _log.warning("open mods dialog failed: %s", e)

    @property
    def service(self) -> ModuleManagerService:
        return self._svc
