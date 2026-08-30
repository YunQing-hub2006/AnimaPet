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
from collections import OrderedDict
from dataclasses import dataclass, field

from anima.utils import jsonio, log, paths

_log = log.get("loader")

VALID_TYPES = ("card", "character", "anim", "emote", "idle", "behavior", "feature", "ui")

#: card 展开时逐文件校验的最大条目数(表情/规则/台词段), 防坏数据拖垮扫描。
_VALIDATE_LIMIT = 1000


# ----------------------------------------------------------------------
# 帧缓存: 全局 LRU + 字节预算
# ----------------------------------------------------------------------
# 原先每个 AnimMod 自带 _cache 且永不释放: 表情动画(angry/disdain 共 119 帧)
# 播完就再没人用, 却和 idle/talk 一起常驻。改为所有动画共用一个预算, 超限
# 时淘汰最久未用的一组。
#
# 正在播放的帧组由 Animator 持有列表引用, 即便从本缓存淘汰也不会立刻释放
# —— 这是有意的: 淘汰只影响"下次是否要重新解码", 不会打断当前动画。
# 因此 _frame_bytes 是估算值, 预算表现为软上限。
# 64MB 的取值: 默认尺寸 240px 下四组动画约 53MB, 全部常驻 -> 切动画零重解码;
# 放大到 320px 时约 94MB 会超限, 于是淘汰不常看的情绪动画, 把内存封住。
_FRAME_BUDGET = 64 * 1024 * 1024    # 解码后像素(ARGB 每像素 4 字节)
_frame_lru = OrderedDict()          # (anim_dir, size) -> list[QPixmap]
_frame_bytes = 0


def clear_frame_cache():
    """模组重扫后调用: 盘上素材可能已变, 缓存整体作废。

    正在播放的帧不受影响(Animator 仍持有引用), 下次取帧时重新解码。
    """
    global _frame_bytes
    _frame_lru.clear()
    _frame_bytes = 0
    _log.info("frame cache cleared")


def cache_stats():
    """当前缓存占用, 供诊断/测试使用。返回 (组数, 估算字节)。"""
    return len(_frame_lru), _frame_bytes


def _scaled_size(reader, size):
    """按 KeepAspectRatio 算出目标尺寸(等比装进 size x size 的方框)。"""
    from PyQt6.QtCore import QSize
    orig = reader.size()
    if not orig.isValid() or orig.width() <= 0 or orig.height() <= 0:
        return QSize(size, size)
    ratio = min(size / orig.width(), size / orig.height())
    return QSize(max(1, round(orig.width() * ratio)),
                 max(1, round(orig.height() * ratio)))


def load_scaled_pixmap(path, size):
    """按显示尺寸解码图片, 不经过全分辨率位图。

    关键: ``setScaledSize`` 让解码器直接产出目标尺寸。原写法
    ``QPixmap(path).scaled(...)`` 会先把 2048x2048 的表情图完整解成
    16MB 的位图再缩小 —— 桌宠只用得到 320x320 的那点像素。
    """
    from PyQt6.QtGui import QImageReader, QPixmap
    reader = QImageReader(path)
    reader.setScaledSize(_scaled_size(reader, size))
    img = reader.read()
    if img.isNull():
        return QPixmap()
    return QPixmap.fromImage(img)


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

    def frames(self, size):
        """按显示尺寸取帧序列, 命中全局缓存则直接复用。

        两级省内存:
        1. 解码即缩放(setScaledSize) —— 不产生全分辨率位图, 消除加载尖峰;
        2. 缓存进全局 LRU —— 表情动画用完可被淘汰, 不无限堆积。
        """
        key = (self.dir, size)
        cached = _frame_lru.get(key)
        if cached is not None:
            _frame_lru.move_to_end(key)      # 命中即刷新为最近使用
            return cached

        frames = self._decode_frames(size)
        global _frame_bytes
        _frame_lru[key] = frames
        _frame_bytes += len(frames) * size * size * 4
        self._evict_if_needed()
        return frames

    def _decode_frames(self, size):
        folder = os.path.join(self.dir, "frames")
        try:
            names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".png"))
        except OSError:
            names = []
        frames = []
        for n in names:
            pm = load_scaled_pixmap(os.path.join(folder, n), size)
            if not pm.isNull():
                frames.append(pm)
        if not frames:
            frames = [self._fallback_disc(size)]  # 素材缺失也不崩
        _log.info("anim %s: %d frames @%dpx", self.id, len(frames), size)
        return frames

    @staticmethod
    def _evict_if_needed():
        """超预算就从最久未用的那组开始扔, 至少保留一组(正在用的不能扔)。"""
        global _frame_bytes
        while _frame_bytes > _FRAME_BUDGET and len(_frame_lru) > 1:
            (_, evict_size), evicted = _frame_lru.popitem(last=False)
            _frame_bytes -= len(evicted) * evict_size * evict_size * 4

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
    try:
        hold_ms = max(500, int(e.get("hold_ms", 4000)))
    except (TypeError, ValueError):
        hold_ms = 4000
    return EmoteDef(
        id=key,
        name=str(e.get("name", key)),
        image=str(e.get("image", "")),
        anim=str(e.get("anim", "")),
        hold_ms=hold_ms,
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
    """把角色卡文件夹展开为一组注册表对象(命名空间 id + character 归属)。

    子文件坏数据逐文件降级(Phase 3 校验边界): 单个表情/规则/台词段非法
    -> 丢该项记日志, 其余照常展开 -- 与 YingPet"绝不因坏数据崩溃"一致;
    坏 manifest 本身(scan_mods 层)才整卡报错。
    """
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
                    _log.warning("card %s: 表情 %r 非法(不是对象), 已跳过", card_id, key)
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
        try:
            lo = max(30, int(raw.get("interval_min", 180)))
            hi = max(30, int(raw.get("interval_max", 420)))
        except (TypeError, ValueError):
            _log.warning("card %s: idle.json 间隔字段非法, 用默认 180~420", card_id)
            lo, hi = 180, 420
        mods.append(IdlePack(
            id=card_id + ":idle", dir=d,
            name="%s 的台词包" % data.get("name", card_id), sections=sections,
            interval_min=lo, interval_max=hi,
            description="角色卡 %s 的内置台词" % card_id,
            character=card_id, version=version, raw=raw,
            source_file="idle.json"))

    # 卡内行为: behaviors.json
    beh_path = os.path.join(d, "behaviors.json")
    if os.path.isfile(beh_path):
        raw = jsonio.load(beh_path, {})
        rules = raw.get("rules")
        rules = _valid_rules(rules, card_id) if isinstance(rules, list) else []
        mods.append(BehaviorMod(
            id=card_id + ":behaviors", dir=d,
            name="%s 的行为规则" % data.get("name", card_id),
            rules=rules,
            description="角色卡 %s 的内置行为" % card_id,
            character=card_id, version=version, raw=raw,
            source_file="behaviors.json"))

    return mods


def _valid_rules(rules, card_id):
    """behaviors.json rules 逐条校验降级: on 非空才保留。

    校验通过保留**原始 dict**(模型 extra=ignore 不回写, 规则里的
    ``if`` 等未声明字段原样透传给规则引擎)。
    """
    from anima.models import Behavior
    out = []
    for r in rules[:_VALIDATE_LIMIT]:
        if not isinstance(r, dict):
            _log.warning("card %s: 行为规则非法(不是对象), 已跳过", card_id)
            continue
        try:
            Behavior(**r)
        except Exception as e:
            _log.warning("card %s: 行为规则 %r 校验失败已跳过: %s", card_id, r.get("on"), e)
            continue
        out.append(r)
    if len(rules) > _VALIDATE_LIMIT:
        _log.warning("card %s: 行为规则超过 %d 条, 多余部分忽略", card_id, _VALIDATE_LIMIT)
    return out
