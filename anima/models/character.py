# -*- coding: utf-8 -*-
"""角色卡 Pydantic v2 模型(TD3: 只做加载/保存边界校验)。

一个角色卡(card.* / .chara)文件夹 = 四个 JSON + 两个素材目录:

    manifest.json   CardMeta     人设 + 动画引用(id/version/name/system_prompt/...)
    emotes.json     Expression   表情(键名 → name/image/anim/hold_ms/lines)
    idle.json       IdleLines    空闲台词包(interval_min/max + 分段 lines)
    behaviors.json  Behavior     行为规则(on/when?/cooldown?/then)
    anims/<短名>/    Animation    帧动画目录(frames/*.png 按文件名排序)
    images/                        静态表情图

双名兼容(TD4): CharacterCard.expressions 输入别名 ``emotes``, 且
``{"emotes": {id: {...}}}`` 字典形态与列表形态等价 —— YingPet 物理结构与
规划书 .chara 超集 manifest 互通。

校验边界约定(与 YingPet "绝不因坏数据崩溃"原则一致):
- 本模块的 load_card/save_card 是**整体**校验(工具/向导/编辑器保存把关,
  坏数据报错要明确);
- 运行时 loader(anima.mods.loader._build_card)对子文件坏 → 逐文件降级
  (错误进 registry.errors, 角色卡其余部分照常可用), 两者策略不同是有意的。
"""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from anima.utils import jsonio


def error_text(exc: ValidationError) -> str:
    """把 ValidationError 压成一行式中文友好文本(对话框/日志用)。"""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"])
        parts.append("%s: %s" % (loc or "(根)", err["msg"]))
    return "; ".join(parts)


# ----------------------------------------------------------------------
# 逐文件模型
# ----------------------------------------------------------------------

class CardMeta(BaseModel):
    """manifest.json 级字段(角色卡人设 + 动画引用)。

    idle_anim/talk_anim: 短名 = 卡内动画(anims/<短名>), 含 ``.`` 或 ``:``
    = 外部素材引用(如 anim.idle / card.ying:angry), 空 = 自动回退。
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    format: str = ""           # .chara 规范标记("chara-1"); 空 = 旧 card.* 未标记
    version: str = "1.0.0"
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    idle_anim: str = ""
    talk_anim: str = ""


class Expression(BaseModel):
    """表情(emotes.json 的一项; id 为键名, 如 default/tsundere)。"""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str = ""
    image: str = ""
    anim: str = ""
    hold_ms: int = 4000
    lines: list[str] = Field(default_factory=list)


class Animation(BaseModel):
    """帧动画(anims/<短名>/ 目录约定或外部 anim.* 素材)。"""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)     # 卡内短名或全局 id
    name: str = ""
    fps: int = Field(default=12, ge=1, le=60)
    frames_dir: str = "frames"


class Behavior(BaseModel):
    """行为规则(behaviors.json rules 的一项)。

    ``on`` 必填非空 —— 没有触发事件的规则永远不生效, 视为坏数据报错;
    编辑器新增/更新规则同样经本模型把关。
    """

    model_config = ConfigDict(extra="ignore")

    on: str = Field(min_length=1)
    when: str = ""
    cooldown: int = Field(default=0, ge=0)
    then: list[dict[str, Any]] = Field(default_factory=list)


class IdleLines(BaseModel):
    """空闲台词包(idle.json): 分段台词(default/sit/night/petted/...)。"""

    model_config = ConfigDict(extra="ignore")

    interval_min: int = 180
    interval_max: int = 420
    lines: dict[str, list[str]] = Field(default_factory=dict)


# ----------------------------------------------------------------------
# 聚合视图(规划书附录 A 的 .chara 超集 manifest)
# ----------------------------------------------------------------------

class CharacterCard(BaseModel):
    """角色卡聚合视图: 一个角色卡文件夹的全部内容。

    ``expressions`` 接受别名 ``emotes``; 字典形态 ``{id: {...}}`` 与
    列表形态等价(见 _expressions_from_dict)。
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(min_length=1)
    format: str = ""
    version: str = "1.0.0"
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    idle_anim: str = ""
    talk_anim: str = ""
    animations: list[Animation] = Field(default_factory=list)
    expressions: list[Expression] = Field(
        default_factory=list, validation_alias="emotes")
    idle: IdleLines | None = None
    behaviors: list[Behavior] = Field(default_factory=list)

    @field_validator("expressions", mode="before")
    @classmethod
    def _expressions_from_dict(cls, v):
        """YingPet emotes.json 的 {键: 字段} 字典 → 列表形态。"""
        if isinstance(v, dict):
            out = []
            for key, e in v.items():
                item = dict(e) if isinstance(e, dict) else {}
                item.setdefault("id", str(key))
                out.append(item)
            return out
        return v


# ----------------------------------------------------------------------
# 文件夹 ↔ 聚合模型
# ----------------------------------------------------------------------

def load_card(card_dir: str) -> CharacterCard:
    """从角色卡文件夹聚合出 CharacterCard(整体校验, 坏数据抛 ValueError)。

    缺 manifest.json / 缺 id 抛 ValueError; 字段类型非法抛
    ValueError("manifest.json: ..."), 子文件同理(错误信息带文件名,
    原始 ValidationError 挂在 __cause__ 上)。
    """
    d = str(card_dir)
    mf = os.path.join(d, "manifest.json")
    if not os.path.isfile(mf):
        raise ValueError("不是角色卡文件夹(缺 manifest.json): %s" % d)
    raw = jsonio.load(mf, {})
    if not isinstance(raw, dict) or not str(raw.get("id", "")).strip():
        raise ValueError("manifest.json 缺少 id: %s" % d)

    def _sub(fname: str, build):
        """读子文件并构造; 坏数据转成带文件名的 ValueError。"""
        path = os.path.join(d, fname)
        if not os.path.isfile(path):
            return None
        try:
            return build(jsonio.load(path, {}))
        except ValidationError as e:
            raise ValueError("%s: %s" % (fname, error_text(e))) from e

    expressions = _sub("emotes.json", lambda raw: [
        {**e, "id": str(k)} for k, e in (raw.get("emotes") or {}).items()
        if isinstance(e, dict)])
    idle = _sub("idle.json", lambda raw: IdleLines(**raw))
    behaviors = _sub("behaviors.json", lambda raw: [
        dict(r) for r in (raw.get("rules") or []) if isinstance(r, dict)])

    animations = []
    anims_dir = os.path.join(d, "anims")
    if os.path.isdir(anims_dir):
        for short in sorted(os.listdir(anims_dir)):
            if os.path.isdir(os.path.join(anims_dir, short)):
                animations.append({"id": short})

    data = {
        "id": raw.get("id"), "format": raw.get("format", ""),
        "version": raw.get("version", "1.0.0"),
        "name": raw.get("name", ""), "description": raw.get("description", ""),
        "system_prompt": raw.get("system_prompt", ""),
        "idle_anim": raw.get("idle_anim", ""), "talk_anim": raw.get("talk_anim", ""),
        "animations": animations,
        "expressions": expressions or [],
        "idle": idle,
        "behaviors": behaviors or [],
    }
    try:
        return CharacterCard(**data)
    except ValidationError as e:
        raise ValueError("manifest.json: %s" % error_text(e)) from e


def save_card(card_dir: str, card: CharacterCard, *, set_format: bool = False) -> None:
    """把聚合模型整体写回角色卡文件夹(写前整体校验 = card 本身已合法)。

    只写模型声明的字段 —— manifest 的其余未知字段不保留(需要保留请走
    编辑器的逐文件保存); set_format=True 时把 manifest 标记为 "chara-1"
    (.chara 规范化输出用)。idle 为 None 时不写 idle.json。
    """
    d = str(card_dir)
    os.makedirs(d, exist_ok=True)
    jsonio.save(os.path.join(d, "manifest.json"), {
        "id": card.id, "type": "card",
        "format": "chara-1" if set_format else card.format,
        "version": card.version, "name": card.name,
        "description": card.description, "system_prompt": card.system_prompt,
        "idle_anim": card.idle_anim, "talk_anim": card.talk_anim,
    })
    jsonio.save(os.path.join(d, "emotes.json"), {
        "emotes": {e.id: e.model_dump(exclude={"id"}) for e in card.expressions}})
    if card.idle is not None:
        jsonio.save(os.path.join(d, "idle.json"), card.idle.model_dump())
    jsonio.save(os.path.join(d, "behaviors.json"), {
        "rules": [b.model_dump(exclude_defaults=True) for b in card.behaviors]})
