# -*- coding: utf-8 -*-
"""rule_engine 插件测试: 订阅/条件/冷却/角色归属/动作执行/热重载重订阅。

行为规则回归基准 = YingPet 实测规则集: petted 好感、@idle.this、cooldown。
"""
import json

import pytest

from anima.core import App
from anima.mods.loader import BehaviorMod, IdlePack
from anima.mods.registry import Registry
from anima.plugins.actions import ActionsPlugin
from anima.plugins.config import ConfigPlugin
from anima.plugins.loader import LoaderPlugin
from anima.plugins.rule_engine import RuleEnginePlugin, render_text
from anima.plugins.state import StatePlugin


@pytest.fixture
def pet_app(tmp_path, monkeypatch):
    """带临时 mods/data 的 App, 装好 config/state/actions/loader/rule_engine。"""
    from anima.utils import jsonio, paths
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(paths, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))

    def write_behavior(mid, rules, character=""):
        d = mods_dir / mid
        d.mkdir(exist_ok=True)
        data = {"id": mid, "type": "behavior", "version": "1.0.0", "name": mid, "rules": rules}
        if character:
            data["character"] = character
        (d / "manifest.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    write_behavior("behavior.test", [
        {"on": "test.hello", "when": "state.affinity >= 5",
         "then": [{"state_inc": {"key": "hits", "delta": 1}},
                  {"say": "你好 {event.who}"}]},
        {"on": "test.hello", "cooldown": 3600,
         "then": [{"state_inc": {"key": "cd_hits", "delta": 1}}]},
    ])
    write_behavior("behavior.special", [
        {"on": "test.hello", "then": [{"state_set": {"key": "special", "value": 1}}]},
    ], character="card.other")

    app = App()
    return app, mods_dir, write_behavior


async def start_app(app):
    plugins = [ConfigPlugin(), StatePlugin(), ActionsPlugin(), LoaderPlugin(), RuleEnginePlugin()]
    await app.start(plugins)
    return plugins


async def test_rule_fires_conditions_and_actions(pet_app):
    app, _, _ = pet_app
    await start_app(app)
    actions = app.registry.use("actions")
    reg = app.registry.use("mods")
    said = []
    # 仿 window 的 say 动作: 文本经 render_text 两层处理(插值是动作方的职责)
    actions.register("say", lambda val, ctx, act: said.append(render_text(val, ctx, reg)))

    app.bus.emit("test.hello", {"who": "世界"})
    assert app.registry.use("state").get("hits") is None   # 条件不满足, 不触发

    app.registry.use("state").change("affinity", 10)
    app.bus.emit("test.hello", {"who": "世界"})
    assert app.registry.use("state").get("hits") == 1
    assert said == ["你好 世界"]                        # {event.who} 插值

    # 角色归属: behavior.special 属于 card.other, 当前角色为空时不触发
    assert app.registry.use("state").get("special") is None
    await app.stop()


async def test_cooldown_blocks_refire(pet_app):
    app, _, _ = pet_app
    await start_app(app)
    app.registry.use("state").change("affinity", 10)
    app.bus.emit("test.hello")
    app.bus.emit("test.hello")
    state = app.registry.use("state")
    assert state.get("cd_hits") == 1                    # cooldown 3600s, 第二次被挡
    # 无冷却的规则第二次仍照常
    assert state.get("hits") == 2
    await app.stop()


async def test_set_character_skips_foreign_rules(pet_app):
    app, _, _ = pet_app
    await start_app(app)
    engine = app.registry.use("rule_engine")
    engine.set_character("card.other")
    app.bus.emit("test.hello")
    assert app.registry.use("state").get("special") == 1
    engine.set_character("card.ying")
    app.bus.emit("test.hello")
    assert app.registry.use("state").get("special") == 1  # 换了角色不再触发
    await app.stop()


async def test_rescan_resubscribes_new_events(pet_app):
    app, _, write_behavior = pet_app
    plugins = await start_app(app)
    loader = next(p for p in plugins if p.name == "loader")
    write_behavior("behavior.extra", [
        {"on": "extra.event", "then": [{"state_set": {"key": "extra", "value": 42}}]},
    ])
    loader.rescan()   # 触发 mods.reloaded → 引擎重建订阅
    app.bus.emit("extra.event")
    assert app.registry.use("state").get("extra") == 42
    await app.stop()


async def test_unknown_action_ignored(pet_app):
    app, _, _ = pet_app
    await start_app(app)
    reg = app.registry.use("mods")
    reg.behaviors["behavior.bad"] = BehaviorMod(
        id="behavior.bad", dir="", name="bad",
        rules=[{"on": "bad.event", "then": [{"no_such_action": 1}]}])
    app.bus.emit("bad.event")   # 不抛, 仅告警
    await app.stop()


# ----------------------------------------------------------------------
# render_text: @idle 引用 + {变量} 插值(与 YingPet 行为一致)
# ----------------------------------------------------------------------

def _idle_registry():
    reg = Registry()
    reg.apply([
        IdlePack(id="card.ying:idle", dir="", name="ying 台词", character="card.ying",
                 sections={"default": ["你好呀"], "petted": ["别摸啦"], "sit": ["坐太久啦"]}),
        IdlePack(id="idle.global", dir="", name="全局",
                 sections={"default": ["大家好"], "night": ["夜深了"]}),
    ])
    reg.active_char_id = "card.ying"
    return reg


def test_render_text_idle_this():
    reg = _idle_registry()
    ctx = {"state": {}, "event": {}, "config": {}}
    text = render_text("@idle.this.petted", ctx, reg)
    assert text == "别摸啦"
    # 无匹配段落回退 default
    assert render_text("@idle.this.nothing", ctx, reg) == "你好呀"


def test_render_text_idle_named_pack():
    reg = _idle_registry()
    ctx = {"state": {}, "event": {}, "config": {}}
    # 旧简写: @idle.global.night → idle.global 包(含点的包 id 必须走这个写法)
    assert render_text("@idle.global.night", ctx, reg) == "夜深了"
    # 包里没有的段回退 default
    assert render_text("@idle.global.nothing", ctx, reg) == "大家好"


def test_render_text_interpolation():
    reg = _idle_registry()
    ctx = {"state": {"affinity": 7}, "event": {"affinity": 14}, "config": {"window": {"size": "small"}}}
    assert render_text("好感 {state.affinity} / 本次 {event.affinity}", ctx, reg) == "好感 7 / 本次 14"
    assert render_text("大小 {config.window.size}", ctx, reg) == "大小 small"
    # 未知变量原样保留
    assert render_text("{nope.var} 保留", ctx, reg) == "{nope.var} 保留"
