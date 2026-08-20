# -*- coding: utf-8 -*-
"""模组注册表: 按类型收纳扫描结果, 是运行时读取角色/素材/规则的唯一入口。"""
import random
from collections import OrderedDict

from anima.mods import loader


class Registry:
    def __init__(self):
        self.characters = OrderedDict()   # id -> CharacterMod
        self.anims = OrderedDict()        # id -> AnimMod
        self.emotes = OrderedDict()       # id -> EmoteDef
        self.idle_packs = OrderedDict()   # id -> IdlePack
        self.behaviors = OrderedDict()    # id -> BehaviorMod
        self.features = OrderedDict()     # id -> FeatureMod
        self.uis = OrderedDict()          # id -> UiMod
        self.all_mods = []                # 全部模组对象(含未启用的, 供管理面板)
        self.errors = []
        self.active_char_id = ""          # 当前角色 id(由窗口刷新时同步), 供 @idle.this 解析

    def clear(self):
        for d in (self.characters, self.anims, self.emotes,
                  self.idle_packs, self.behaviors, self.features, self.uis):
            d.clear()
        self.all_mods = []
        self.errors = []

    def apply(self, mods, enabled_ids=None, errors=None):
        """按开关表收纳。enabled_ids: None=全启用, dict={id: bool}(缺省 True)。"""
        self.clear()
        self.errors = list(errors or [])
        for m in mods:
            self.all_mods.append(m)
            if not self._enabled(m.id, enabled_ids):
                continue
            if isinstance(m, loader.CharacterMod):
                self.characters[m.id] = m
            elif isinstance(m, loader.AnimMod):
                self.anims[m.id] = m
            elif isinstance(m, loader.EmoteDef):
                self.emotes[m.id] = m
            elif isinstance(m, loader.IdlePack):
                self.idle_packs[m.id] = m
            elif isinstance(m, loader.BehaviorMod):
                self.behaviors[m.id] = m
            elif isinstance(m, loader.FeatureMod):
                self.features[m.id] = m
            elif isinstance(m, loader.UiMod):
                self.uis[m.id] = m

    @staticmethod
    def _enabled(mid, enabled_ids):
        if enabled_ids is None:
            return True
        return bool(enabled_ids.get(mid, True))

    # ---- 查询 ----
    def emote(self, emote_id):
        return self.emotes.get(emote_id)

    def anim(self, anim_id):
        return self.anims.get(anim_id)

    def character(self, char_id):
        return self.characters.get(char_id)

    # ---- 角色归属查询 (v3.2: character 字段为空 = 全局, 对所有角色生效) ----
    @staticmethod
    def _for_char(mapping, char_id):
        """当前角色专属 + 全局(character 为空)项, 保持注册顺序。"""
        cid = str(char_id or "")
        return OrderedDict(
            (k, m) for k, m in mapping.items()
            if not getattr(m, "character", "") or getattr(m, "character", "") == cid)

    def character_emotes(self, char_id):
        """该角色可用表情: 专属 + 全局。"""
        return self._for_char(self.emotes, char_id)

    def character_behaviors(self, char_id):
        """该角色生效的行为模组: 专属 + 全局。"""
        return self._for_char(self.behaviors, char_id)

    def character_idle_packs(self, char_id):
        """该角色可用台词包: 专属 + 全局。"""
        return self._for_char(self.idle_packs, char_id)

    def character_idle(self, char_id):
        """当前角色专属台词包优先, 其次全局包, 都没有才退回任意包。"""
        cid = str(char_id or "")
        exact = global_pack = None
        for p in self.idle_packs.values():
            pc = str(getattr(p, "character", "") or "")
            if pc == cid and exact is None:
                exact = p
            elif pc == "" and global_pack is None:
                global_pack = p
        if exact is not None:
            return exact
        if global_pack is not None:
            return global_pack
        return next(iter(self.idle_packs.values())) if self.idle_packs else None

    def ui(self, ui_id=None):
        """取当前皮肤: 优先 ui_id(来自 config mods.ui), 否则第一个启用的, 无则 None(用默认主题)。"""
        if ui_id:
            m = self.uis.get(ui_id)
            if m:
                return m
        for m in self.uis.values():
            return m
        return None

    def emote_lines(self, emote_id):
        e = self.emotes.get(emote_id)
        return (e.lines if e else []) or ["……"]

    def idle_line(self, pack_id, section="default"):
        """从空闲台词包随机取一句。"""
        p = self.idle_packs.get(pack_id)
        if not p:
            return None
        lines = p.sections.get(section) or p.sections.get("default") or []
        return random.choice(lines) if lines else None

    def idle_interval(self, char_id=""):
        """当前角色专属台词包的搭话间隔优先(v3.2), 无包时用默认 180~420。"""
        p = self.character_idle(char_id)
        if p is not None:
            return p.interval_min, p.interval_max
        return 180, 420
