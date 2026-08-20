# -*- coding: utf-8 -*-
"""全链路集成测试: 真实 mods 数据 + 完整插件栈 + offscreen Qt。

覆盖: 启动→加载(19 个模组对象)→窗口绑定→规则触发→功能模组运行时启停→
TD1 真双线程 run_on_ui 队列封送→停止清理。
"""
import asyncio
import os
import threading
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

import main
from anima.utils import jsonio, paths

SIT_LINES = [
    "坐太久了。起来活动一下, 别让身体比我还先坏掉。",
    "时间差不多咯——我是说, 该起来走走了。",
    "一直坐着可打不了仗。起来, 伸展一下。",
]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def real_env(tmp_path, monkeypatch):
    """真实 mods/(仓库 E: 盘)+ 重定向 data(tmp 在 C: 盘): 两者无法同处一个
    项目根守卫内, 故测试内放行 _guard(仅本测试生效, 语义=接受任意绝对路径)。"""
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_guard", lambda path: os.path.normpath(os.path.abspath(path)))


async def test_full_stack_boots_with_real_mods(real_env, qapp):
    core, plugins, pet, _bridge = main._build_stack()
    await core.start(plugins)

    reg = core.registry.use("mods")
    # 真实数据: card.ying 展开(4 动画+角色+8 表情+台词+行为) + health + 3 皮肤 + 6 功能模组 = 25
    assert len(reg.all_mods) == 25
    assert reg.errors == []
    assert reg.characters.get("card.ying")
    assert len(reg.anims) == 4
    assert len(reg.emotes) == 8
    assert reg.idle_packs and reg.behaviors
    assert len(reg.features) == 6
    assert len(reg.uis) == 3

    # 窗口已绑定并刷出真实帧(offscreen QPixmap 解码 PNG)
    assert pet.char is not None and pet.char.id == "card.ying"
    assert len(pet.animator.idle_frames) > 0
    assert len(pet.animator.talk_frames) > 0

    # 动作注册表: 内置 + 窗口表现动作
    actions = core.registry.use("actions")
    assert {"say", "emote", "anim", "state_inc", "state_set", "emit"} <= set(actions.names())

    # feature.hello 已自动启用, 菜单齐备
    assert core.lifecycle.get_state("feature.hello") == "enabled"
    labels = [lbl for lbl, _ in pet.feature_menu]
    assert "模组管理" in labels and "打个招呼 (插件)" in labels

    # 规则全链路: petted 好感(卡内行为, when event.affinity % 20 == 0)
    core.registry.use("state").change("affinity", 0)
    core.bus.emit("pet.petted", {"affinity": 20})
    assert pet.bubble._full.startswith("……好感度 20")

    # @idle.this: 全局行为 behavior.health 引用当前角色台词包
    core.bus.emit("timer.sit")
    assert pet.bubble._full in SIT_LINES

    # 窗口摸头路径: 好感 +1 并广播(规则不满足 %20 时走 @idle.this.petted)
    pet._on_petted()
    assert core.registry.use("state").get("affinity") == 1

    await core.stop()
    assert core.lifecycle.get_state("feature.hello") == "unloaded"
    assert core.bus.count() == 0   # 副作用全回滚


async def test_real_feature_runtime_toggle(real_env, qapp):
    core, plugins, pet, _bridge = main._build_stack()
    await core.start(plugins)
    mm = core.registry.use("module_manager")

    await mm.set_enabled("feature.hello", False)
    assert core.lifecycle.get_state("feature.hello") == "unloaded"
    assert "打个招呼 (插件)" not in [lbl for lbl, _ in pet.feature_menu]

    await mm.set_enabled("feature.hello", True)
    assert core.lifecycle.get_state("feature.hello") == "enabled"
    assert "打个招呼 (插件)" in [lbl for lbl, _ in pet.feature_menu]
    await core.stop()


def test_td1_cross_thread_run_on_ui(real_env, qapp):
    """TD1 验收: 内核线程经 bridge.run_on_ui 队列封送到 Qt 主线程。"""
    core, plugins, pet, bridge = main._build_stack()
    holder = {"loop": None, "started": threading.Event(), "error": None}
    thread = threading.Thread(
        target=main._kernel_main, args=(core, plugins, holder),
        daemon=True, name="anima-kernel-test")
    thread.start()
    try:
        assert holder["started"].wait(15)
        assert holder["error"] is None
        loop = holder["loop"]
        assert loop is not None

        async def _say_from_kernel():
            bridge.say("跨线程台词")

        fut = asyncio.run_coroutine_threadsafe(_say_from_kernel(), loop)
        fut.result(10)

        # 主线程泵事件循环: 队列信号在此执行
        for _ in range(100):
            if pet.bubble._full == "跨线程台词":
                break
            qapp.processEvents()
            time.sleep(0.01)
        assert pet.bubble._full == "跨线程台词"
    finally:
        loop = holder.get("loop")
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread.join(10)
    assert not thread.is_alive()


def test_rescan_from_qt_thread_goes_to_kernel(real_env, qapp):
    """A2 回归: Qt 线程调 mm.rescan() 不得直改注册表(竞态), 必须经内核循环
    调度并等待完成; 重扫后规则索引/订阅仍生效。"""
    core, plugins, pet, _bridge = main._build_stack()
    reloaded = []
    core.bus.subscribe("mods.reloaded", lambda d: reloaded.append(d))
    holder = {"loop": None, "started": threading.Event(), "error": None}
    thread = threading.Thread(
        target=main._kernel_main, args=(core, plugins, holder),
        daemon=True, name="anima-kernel-test")
    thread.start()
    try:
        assert holder["started"].wait(15)
        assert holder["error"] is None

        mm = core.registry.use("module_manager")
        fut = mm.rescan()          # 本线程是 Qt 主线程, 非内核线程 → 调度到内核循环
        assert fut is not None
        fut.result(10)             # 内核线程完成重扫

        assert reloaded             # mods.reloaded 已在内核线程发出
        assert len(core.registry.use("mods").all_mods) == 25
        assert core.lifecycle.get_state("feature.hello") == "enabled"

        # 重扫后规则引擎索引重建且可用(emit 走 Qt 线程, 无并发写注册表)
        core.bus.emit("timer.sit")
        assert pet.bubble._full in SIT_LINES
    finally:
        loop = holder.get("loop")
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread.join(10)
    assert not thread.is_alive()
