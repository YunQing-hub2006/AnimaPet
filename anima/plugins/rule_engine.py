# -*- coding: utf-8 -*-
"""rule_engine 插件: 事件 → 条件 → 动作。行为模组只声明 JSON 规则, 引擎负责匹配执行。

服务名 ``"rule_engine"``。搬运自 YingPet-v4 core/rule_engine.py, 改写点:

1. ``bus.on_all`` 用内核总线替代: 内核通配订阅 ``"*"`` 的 handler 只收到 payload、
   收不到事件名, 而规则匹配需要事件名, 因此改为**按规则声明的事件名逐个订阅**
   (语义与 on_all+过滤完全等价, 且更省开销); 订阅在 ``refresh()`` 里随注册表重建。
2. 动作执行走 actions 服务(``ctx.use("actions")`` 的 ActionRegistry)。
3. 求值上下文补了 ``config`` 键(YingPet 里 safe_eval 支持 config.* 但规则 ctx 没给,
   顺手补齐); state 服务的数据 dict 每事件快照。
4. ``@idle.this`` / ``@idle.<包id>.<段>`` 模板与 cooldown 语义原样保留。

规则格式::

    {"on": "timer.night", "when": "time >= 23:00", "cooldown": 3600,
     "then": [{"say": "台词 {event.affinity}"}, {"emote": "tsundere"}]}
"""
from __future__ import annotations

import random
import re
import time

from anima.core import Plugin, Context
from anima.events import EventNames
from anima.plugins import safe_eval
from anima.utils import log

_log = log.get("rules")


def render_text(text, ctx, registry):
    """把动作里的文本做两层处理: @idle 引用 → 随机台词; {变量} → 取值插值。

    @idle.this.<段>  = 当前角色自己的台词包(角色卡内行为规则推荐写法, 换卡不用改)
    @idle.<包id>.<段> = 指定台词包(兼容 @idle.ying.x → idle.ying 包的旧简写)
    """
    text = str(text)
    if text.startswith("@idle."):
        parts = text[6:].split(".")
        pack = parts[0]
        section = parts[1] if len(parts) > 1 else "default"
        if pack == "this":
            line = _this_idle_line(registry, section)
        else:
            line = registry.idle_line(pack, section)
            if line is None and not pack.startswith("idle."):
                # 兼容简写: @idle.ying.night → idle.ying 包
                line = registry.idle_line("idle." + pack, section)
        if line:
            text = line

    def repl(m):
        v = _resolve_path(m.group(1), ctx)
        return str(v) if v is not None else m.group(0)

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}", repl, text)


def _this_idle_line(registry, section):
    """@idle.this: 从当前角色的台词包(专属优先, 其次全局)取一句。"""
    p = registry.character_idle(getattr(registry, "active_char_id", ""))
    if p is None:
        return None
    lines = p.sections.get(section) or p.sections.get("default") or []
    return random.choice(lines) if lines else None


def _resolve_path(path, ctx):
    parts = path.split(".")
    if len(parts) >= 2 and parts[0] in ("state", "event", "config"):
        cur = ctx.get(parts[0])
        for p in parts[1:]:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur
    return None


class RuleEngine:
    """订阅规则声明的事件; 对每条启用的行为规则做 事件匹配 → 条件求值 → 执行动作。"""

    def __init__(self, debug_rules: bool = False):
        self._bus = None
        self._reg = None
        self._state = None
        self._config = None
        self._exec = None
        self._debug_rules = bool(debug_rules)
        self._char_id = ""       # 当前角色 id, 由运行时刷新时同步
        self._last_fired = {}    # (mod_id, rule_idx) -> ts
        self._subscribed = {}    # event -> handler(供 refresh 差量重建)
        self._index = {}         # event -> [(mod, idx, rule)](分发索引, refresh 重建)

    def bind(self, bus, registry, state, config, actions, debug_rules=None):
        """接入总线/注册表/状态/配置/动作注册表(插件 enable 阶段调用)。"""
        self._bus = bus
        self._reg = registry
        self._state = state
        self._config = config
        self._exec = actions
        if debug_rules is not None:
            self._debug_rules = bool(debug_rules)
        self.refresh()

    # ------------------------------------------------------------------
    # 订阅维护
    # ------------------------------------------------------------------

    def refresh(self):
        """按当前启用行为规则重建 事件索引 + 订阅(注册表热重载后调用)。"""
        if self._bus is None or self._reg is None:
            return
        events = set()
        index = {}
        for mod in self._reg.behaviors.values():
            for idx, rule in enumerate(mod.rules):
                if not isinstance(rule, dict):
                    continue
                on = rule.get("on")
                if isinstance(on, str):
                    names = [on]
                elif isinstance(on, list):
                    names = [str(x) for x in on]
                else:
                    names = []
                for n in names:
                    events.add(n)
                    index.setdefault(n, []).append((mod, idx, rule))
        self._index = index
        for ev, handler in list(self._subscribed.items()):
            if ev not in events:
                self._bus.unsubscribe(ev, handler)
                del self._subscribed[ev]
        for ev in sorted(events):
            if ev in self._subscribed:
                continue
            handler = (lambda payload, e=ev: self._handle(e, payload))
            self._bus.subscribe(ev, handler)
            self._subscribed[ev] = handler
        _log.info("rules subscribed: %d events, %d rules indexed",
                  len(self._subscribed), sum(len(v) for v in index.values()))

    def unsubscribe_all(self):
        """退订全部事件(插件 disable/unload 清理)。"""
        if self._bus is None:
            return
        for ev, handler in list(self._subscribed.items()):
            self._bus.unsubscribe(ev, handler)
        self._subscribed.clear()
        self._index = {}

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def set_character(self, char_id):
        """同步当前角色 id; 行为模组声明了 character 且不匹配的将被跳过。"""
        self._char_id = str(char_id or "")

    def _handle(self, name, payload):
        try:
            entries = self._index.get(name)
            if not entries:
                return
            ctx = None   # 懒快照: 每条事件只建一次, 且仅当确有规则需要
            for mod, idx, rule in entries:
                # 角色归属: 声明了 character 且 ≠ 当前角色的模组不触发; 全局(空)不受影响
                if mod.character and mod.character != self._char_id:
                    continue
                if ctx is None:
                    ctx = {"state": dict(self._state.data),
                           "event": dict(payload or {}),
                           "config": dict(self._config.data)}
                self._try_rule(mod.id, idx, rule, name, payload, ctx)
        except Exception as e:
            _log.warning("rule dispatch failed: %s", e)

    def _try_rule(self, mod_id, idx, rule, name, payload, ctx):
        events = rule.get("on")
        if isinstance(events, str):
            events = [events]
        if not isinstance(events, list) or name not in events:
            return
        try:
            cooldown = max(0, int(rule.get("cooldown", 0)))
        except (TypeError, ValueError):
            cooldown = 0
        key = (mod_id, idx)
        if cooldown > 0 and time.time() - self._last_fired.get(key, 0) < cooldown:
            return
        for cond_key in ("when", "if"):
            cond = rule.get(cond_key)
            if cond is None or str(cond).strip() == "":
                continue
            ok, status = safe_eval.evaluate_detailed(str(cond), ctx)
            if self._debug_rules:
                _log.info("[rules-debug] rule=%s#%d %s=%r => %s",
                          mod_id, idx, cond_key, str(cond),
                          "true" if ok else ("parse_error" if status == "parse_error" else "false"))
            if not ok:
                return
        actions = rule.get("then")
        if not isinstance(actions, list):
            actions = []
        self._last_fired[key] = time.time()
        _log.info("rule fired: %s#%d on %s", mod_id, idx, name)
        for action in actions:
            if not isinstance(action, dict):
                continue
            try:
                self._run_action(action, ctx)
            except Exception as e:
                _log.warning("action failed %r: %s", action, e)

    def _run_action(self, action, ctx):
        name = next(iter(action), None)
        fn = self._exec.get(name)
        if fn is None:
            _log.warning("未知动作 %r, 已忽略", name)
            return
        fn(action[name], ctx, action)


class RuleEnginePlugin(Plugin):
    """规则引擎插件: provide 引擎实例, mods.reloaded 时重建订阅。"""

    name = "rule_engine"
    version = "1.0.0"
    dependencies = ["state", "actions", "loader"]

    def __init__(self, engine: RuleEngine | None = None) -> None:
        self._engine = engine if engine is not None else RuleEngine()
        self._ctx: Context | None = None

    async def load(self, ctx: Context) -> None:
        self._ctx = ctx
        ctx.provide("rule_engine", self._engine)
        ctx.on(EventNames.MODS_RELOADED, lambda _data: self._engine.refresh())

    async def enable(self) -> None:
        assert self._ctx is not None
        cfg = self._ctx.use("config")
        self._engine.bind(
            bus=self._ctx.app.bus,
            registry=self._ctx.use("mods"),
            state=self._ctx.use("state"),
            config=cfg,
            actions=self._ctx.use("actions"),
            debug_rules=bool(cfg.get("debug.rules", False)),
        )

    async def disable(self) -> None:
        self._engine.unsubscribe_all()

    @property
    def engine(self) -> RuleEngine:
        return self._engine
