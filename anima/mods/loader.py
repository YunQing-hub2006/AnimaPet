# -*- coding: utf-8 -*-
"""模组加载器: 扫描 mods/*/manifest.json, 校验并构造成注册表对象。

模组类型 (manifest.type):
    card       角色卡(自包含: 人设+动画+表情+台词+行为, v4 推荐)
    character  角色卡(旧式, 引用外部素材)   anim   序列帧动画集
    emote      表情(单张或打包)            idle   空闲台词包
    behavior   行为规则                   feature 功能插件(Python 代码)
    ui         皮肤主题

角色卡文件夹结构 (type=card):
    manifest.json   人设 + idle_anim/talk_anim(短名 = 卡内动画, 带点 = 外部引用)
    anims/<短名>/frames/*.png
    emotes.json     {"emotes": {...}}   (表情键名不带前缀, 如 default/tsundere)
    idle.json       {"interval_min": 180, "interval_max": 420, "lines": {...}}
    behaviors.json  {"rules": [...]}    (@idle.this.<段> 引用本卡台词包)
卡内素材注册为命名空间 id: <卡id>:<短名>, 归属隔离由 character 字段保证。
"""
import os
from dataclasses import dataclass, field

from anima.utils import jsonio, log, paths

_log = log.get("loader")

VALID_TYPES = ("card", "character", "anim", "emote", "idle", "behavior", "feature", "ui")


# ----------------------------------------------------------------------
# 模组对象
# ----------------------------------------------------------------------

@dataclass
class AnimMod:
    """序列帧动画集: frames/ 下按文件名排序的 PNG 序列。"""
    id: str
    dir: str
    name: str = ""
    fps: int = 12
    description: str = ""
    version: str = ""
    _cache: dict = field(default_factory=dict, repr=False)

    def frames(self, size):
        """懒加载: 第一次用到时才读盘+缩放, 之后命中缓存(轻量化的关键)。"""
        cached = self._cache.get(size)
        if cached is not None:
            return cached
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap
        folder = os.path.join(self.dir, "frames")
        names = []
        try:
            names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".png"))
        except OSError:
            pass
        frames = []
        for n in names:
            pm = QPixmap(os.path.join(folder, n))
            if pm.isNull():
                continue
            frames.append(pm.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        if not frames:
            frames = [self._fallback_disc(size)]  # 素材缺失也不崩
        self._cache[size] = frames
        _log.info("anim %s: %d frames @%dpx", self.id, len(frames), size)
        return frames

    @staticmethod
    def _fallback_disc(size):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QPainter, QPixmap
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        qp = QPainter(pm)
        qp.setBrush(QColor(120, 40, 70))
        qp.setPen(Qt.PenStyle.NoPen)
        qp.drawEllipse(4, 4, size - 8, size - 8)
        qp.end()
        return pm


@dataclass
class EmoteDef:
    """表情: 静态图(image) 或 引用动画集(anim), 附本地台词。

    character: 归属角色 id(v3.2); 空 = 全局表情, 对所有角色可用。
    粒度按整包标记: 表情包 manifest 的 character 字段作用于包内全部表情。
    """
    id: str
    name: str
    image: str = ""
    anim: str = ""
    hold_ms: int = 4000
    lines: list = field(default_factory=list)
    owner_dir: str = ""
    description: str = ""
    character: str = ""
    version: str = ""
    raw: dict = field(default_factory=dict, repr=False)  # 所属数据源原文, 供回写
    source_file: str = "manifest.json"  # 回写目标文件(角色卡内为 emotes.json)


@dataclass
class CharacterMod:
    """角色卡: 人设 prompt + 默认动画集。"""
    id: str
    dir: str
    name: str
    system_prompt: str
    description: str = ""
    idle_anim: str = "anim.idle"
    talk_anim: str = "anim.talk"
    version: str = ""
    raw: dict = field(default_factory=dict, repr=False)  # 原始 manifest, 供设置界面回写


@dataclass
class IdlePack:
    """空闲台词包: 分段台词(default/sit/night/petted/...)。

    character: 归属角色 id(v3.2); 空 = 全局包, 对所有角色可用。
    """
    id: str
    dir: str = ""
    name: str = ""
    sections: dict = field(default_factory=dict)
    interval_min: int = 180
    interval_max: int = 420
    description: str = ""
    character: str = ""
    version: str = ""
    raw: dict = field(default_factory=dict, repr=False)  # 原始数据源, 供角色管理器回写
    source_file: str = "manifest.json"  # 回写目标文件(角色卡内为 idle.json)


@dataclass
class BehaviorMod:
    """行为规则: rules = [{on, when?, if?, cooldown?, then: [动作...]}]

    character: 归属角色 id(v3.2); 空 = 全局规则, 对所有角色生效。
    """
    id: str
    dir: str
    name: str = ""
    rules: list = field(default_factory=list)
    description: str = ""
    character: str = ""
    version: str = ""
    raw: dict = field(default_factory=dict, repr=False)  # 原始数据源, 供角色管理器回写
    source_file: str = "manifest.json"  # 回写目标文件(角色卡内为 behaviors.json)


@dataclass
class FeatureMod:
    """功能插件: 可携带 Python 代码(plugin.py), 经内核 Plugin 契约接入。"""
    id: str
    dir: str
    name: str = ""
    main: str = "plugin.py"
    instance: object = None
    description: str = ""
    version: str = ""


@dataclass
class UiMod:
    """皮肤模组: theme 为颜色/字体/气泡配色字典, 覆盖聊天面板默认主题。"""
    id: str
    dir: str
    name: str = ""
    theme: dict = field(default_factory=dict)
    description: str = ""
    version: str = ""


# ----------------------------------------------------------------------
# 扫描
# ----------------------------------------------------------------------

def scan_mods():
    """扫描 mods/ 下所有带 manifest.json 的子目录。返回 (mods, errors)。"""
    mods = []
    errors = []
    if not os.path.isdir(paths.MODS_DIR):
        return mods, errors
    for name in sorted(os.listdir(paths.MODS_DIR)):
        d = os.path.join(paths.MODS_DIR, name)
        if not os.path.isdir(d):
            continue
        mf = os.path.join(d, "manifest.json")
        if not os.path.isfile(mf):
            continue
        try:
            data = jsonio.load(mf, {})
            built = _build_mods(d, data)
            mods.extend(built)
        except Exception as e:
            errors.append((name, str(e)))
            _log.warning("mod %s 加载失败: %s", name, e)
    return mods, errors


def _build_mods(d, data):
    mtype = str(data.get("type", "")).strip().lower()
    mid = str(data.get("id", "")).strip()
    if not mid:
        raise ValueError("manifest 缺少 id")
    if mtype not in VALID_TYPES:
        raise ValueError("未知类型 %r (合法: %s)" % (mtype, "/".join(VALID_TYPES)))
    if mtype == "character":
        return [CharacterMod(
            id=mid, dir=d, name=str(data.get("name", mid)),
            system_prompt=str(data.get("system_prompt", "")),
            description=str(data.get("description", "")),
            idle_anim=str(data.get("idle_anim", "anim.idle")),
            talk_anim=str(data.get("talk_anim", "anim.talk")),
            version=str(data.get("version", "")),
            raw=data,
        )]
    if mtype == "card":
        return _build_card(d, data, mid)
    if mtype == "anim":
        return [AnimMod(id=mid, dir=d, name=str(data.get("name", mid)),
                        fps=max(1, int(data.get("fps", 12))),
                        description=str(data.get("description", "")),
                        version=str(data.get("version", "")))]
    if mtype == "emote":
        return _build_emotes(d, data)
    if mtype == "idle":
        lines = data.get("lines")
        if isinstance(lines, dict):
            sections = {k: [str(x) for x in (v or []) if str(x).strip()]
                        for k, v in lines.items()}
        elif isinstance(lines, list):
            sections = {"default": [str(x) for x in lines if str(x).strip()]}
        else:
            sections = {}
        return [IdlePack(
            id=mid, dir=d, name=str(data.get("name", mid)), sections=sections,
            interval_min=max(30, int(data.get("interval_min", 180))),
            interval_max=max(30, int(data.get("interval_max", 420))),
            description=str(data.get("description", "")),
            character=str(data.get("character", "")),
            version=str(data.get("version", "")),
            raw=data,
        )]
    if mtype == "behavior":
        rules = data.get("rules")
        return [BehaviorMod(id=mid, dir=d, name=str(data.get("name", mid)),
                            rules=rules if isinstance(rules, list) else [],
                            description=str(data.get("description", "")),
                            character=str(data.get("character", "")),
                            version=str(data.get("version", "")),
                            raw=data,)]
    if mtype == "feature":
        return [FeatureMod(id=mid, dir=d, name=str(data.get("name", mid)),
                           main=str(data.get("main", "plugin.py")),
                           description=str(data.get("description", "")),
                           version=str(data.get("version", "")))]
    if mtype == "ui":
        theme = data.get("theme")
        return [UiMod(id=mid, dir=d, name=str(data.get("name", mid)),
                      theme=theme if isinstance(theme, dict) else {},
                      description=str(data.get("description", "")),
                      version=str(data.get("version", "")))]
    return []


def _build_emotes(d, data):
    """表情支持两种写法: 单表情模组 或 表情包(emotes 字典)。

    character 按整包标记(v3.2 决策): 写在表情模组 manifest 顶层, 作用于包内全部表情。
    """
    out = []
    character = str(data.get("character", ""))
    version = str(data.get("version", ""))
    pack = data.get("emotes")
    if isinstance(pack, dict):
        for key, e in pack.items():
            if not isinstance(e, dict):
                continue
            out.append(_one_emote(str(key), e, d, data, character, version))
    else:
        out.append(_one_emote(str(data.get("id", "")), data, d, data, character, version))
    return [e for e in out if e.id]


def _one_emote(key, e, d, raw, character="", version=""):
    return EmoteDef(
        id=key,
        name=str(e.get("name", key)),
        image=str(e.get("image", "")),
        anim=str(e.get("anim", "")),
        hold_ms=max(500, int(e.get("hold_ms", 4000))),
        lines=[str(x) for x in (e.get("lines") or []) if str(x).strip()],
        owner_dir=d,
        description=str(e.get("description", "")),
        character=character,
        version=version,
        raw=raw,
    )


# ----------------------------------------------------------------------
# 角色卡 (type=card): 一个文件夹 = 一个角色的全部
# ----------------------------------------------------------------------

def _resolve_anim_ref(card_id, value, fallback):
    """卡内动画引用: 短名 → <卡id>:<短名>; 含 . 或 : → 视为外部绝对 id。"""
    v = str(value or "").strip()
    if not v:
        return fallback
    if "." in v or ":" in v:
        return v
    return "%s:%s" % (card_id, v)


def _build_card(d, data, card_id):
    """把角色卡文件夹展开为一组注册表对象(命名空间 id + character 归属)。"""
    version = str(data.get("version", ""))
    mods = []

    # 卡内动画: anims/<短名>/frames/*.png
    anims_dir = os.path.join(d, "anims")
    internal_anims = {}
    if os.path.isdir(anims_dir):
        for short in sorted(os.listdir(anims_dir)):
            adir = os.path.join(anims_dir, short)
            if not os.path.isdir(adir):
                continue
            aid = "%s:%s" % (card_id, short)
            internal_anims[short] = aid
            mods.append(AnimMod(
                id=aid, dir=adir, name="%s · %s" % (data.get("name", card_id), short),
                description="角色卡 %s 的内置动画" % card_id,
                version=version))

    char = CharacterMod(
        id=card_id, dir=d, name=str(data.get("name", card_id)),
        system_prompt=str(data.get("system_prompt", "")),
        description=str(data.get("description", "")),
        idle_anim=_resolve_anim_ref(card_id, data.get("idle_anim"),
                                    internal_anims.get("idle", "")),
        talk_anim=_resolve_anim_ref(card_id, data.get("talk_anim"),
                                    internal_anims.get("talk", "")),
        version=version,
        raw=data,
    )
    mods.append(char)

    # 卡内表情: emotes.json {"emotes": {...}}
    emotes_path = os.path.join(d, "emotes.json")
    if os.path.isfile(emotes_path):
        raw = jsonio.load(emotes_path, {})
        pack = raw.get("emotes")
        if isinstance(pack, dict):
            for key, e in pack.items():
                if not isinstance(e, dict):
                    continue
                em = _one_emote(str(key), e, d, raw, character=card_id, version=version)
                em.source_file = "emotes.json"
                if em.id:
                    mods.append(em)

    # 卡内台词: idle.json
    idle_path = os.path.join(d, "idle.json")
    if os.path.isfile(idle_path):
        raw = jsonio.load(idle_path, {})
        lines = raw.get("lines")
        if isinstance(lines, dict):
            sections = {k: [str(x) for x in (v or []) if str(x).strip()]
                        for k, v in lines.items()}
        elif isinstance(lines, list):
            sections = {"default": [str(x) for x in lines if str(x).strip()]}
        else:
            sections = {}
        mods.append(IdlePack(
            id=card_id + ":idle", dir=d,
            name="%s 的台词包" % data.get("name", card_id), sections=sections,
            interval_min=max(30, int(raw.get("interval_min", 180))),
            interval_max=max(30, int(raw.get("interval_max", 420))),
            description="角色卡 %s 的内置台词" % card_id,
            character=card_id, version=version, raw=raw,
            source_file="idle.json"))

    # 卡内行为: behaviors.json
    beh_path = os.path.join(d, "behaviors.json")
    if os.path.isfile(beh_path):
        raw = jsonio.load(beh_path, {})
        rules = raw.get("rules")
        mods.append(BehaviorMod(
            id=card_id + ":behaviors", dir=d,
            name="%s 的行为规则" % data.get("name", card_id),
            rules=rules if isinstance(rules, list) else [],
            description="角色卡 %s 的内置行为" % card_id,
            character=card_id, version=version, raw=raw,
            source_file="behaviors.json"))

    return mods
