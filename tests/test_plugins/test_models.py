# -*- coding: utf-8 -*-
"""Phase 3 模型层测试: Pydantic 模型 / load_card / save_card / schema 漂移。"""
import json
import os
import shutil

import pytest
from pydantic import ValidationError

from anima.models import (
    Animation,
    Behavior,
    CharacterCard,
    Expression,
    IdleLines,
    error_text,
    load_card,
    save_card,
)
from anima.utils import jsonio, paths


# ----------------------------------------------------------------------
# 模型
# ----------------------------------------------------------------------

def test_emotes_alias_dict_equivalent_list():
    a = CharacterCard(id="card.x", emotes={"a": {"name": "A"}})
    b = CharacterCard(id="card.x", expressions=[{"id": "a", "name": "A"}])
    assert a.expressions[0].id == "a"
    assert a.expressions[0].name == "A"
    assert a.expressions == b.expressions


def test_behavior_on_required_nonempty():
    with pytest.raises(ValidationError):
        Behavior(on="")


def test_behavior_then_arbitrary_dict_ok():
    b = Behavior(on="pet.petted", then=[{"say": "@idle.this.default"}, {"custom": {"x": 1}}])
    assert b.on == "pet.petted"
    assert len(b.then) == 2


def test_animation_fps_range():
    with pytest.raises(ValidationError):
        Animation(id="a", fps=0)
    with pytest.raises(ValidationError):
        Animation(id="a", fps=61)
    assert Animation(id="a", fps=1).fps == 1
    assert Animation(id="a", fps=60).fps == 60


def test_idle_lines_defaults():
    idle = IdleLines()
    assert idle.interval_min == 180 and idle.interval_max == 420
    assert idle.lines == {}


def test_error_text_is_readable():
    try:
        CharacterCard(id="")
    except ValidationError as e:
        text = error_text(e)
        assert "id" in text


# ----------------------------------------------------------------------
# load_card 整体校验
# ----------------------------------------------------------------------

def test_load_card_real_card_aggregate():
    card = load_card(os.path.join(paths.MODS_DIR, "card.ying"))
    assert card.id == "card.ying"
    assert card.name
    assert len(card.expressions) >= 5          # 真实卡 8 个表情
    assert "default" in [e.id for e in card.expressions]
    assert card.idle is not None
    assert "default" in card.idle.lines
    assert len(card.behaviors) >= 3
    short_names = [a.id for a in card.animations]
    assert "angry" in short_names             # 真卡 anims/angry


def test_load_card_missing_manifest_raises(tmp_path):
    with pytest.raises(ValueError, match="manifest"):
        load_card(str(tmp_path / "empty"))


def test_load_card_missing_id_raises(tmp_path, monkeypatch):
    d = tmp_path / "bad"
    d.mkdir()
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    (d / "manifest.json").write_text(json.dumps({"type": "card"}), encoding="utf-8")
    with pytest.raises(ValueError, match="id"):
        load_card(str(d))


# ----------------------------------------------------------------------
# save_card 往返
# ----------------------------------------------------------------------

def test_save_card_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    d = tmp_path / "card"
    card = CharacterCard(
        id="card.round", name="往返", description="desc",
        system_prompt="人设", idle_anim="idle", talk_anim="talk",
        expressions=[{"id": "default", "name": "平时", "lines": ["hi"]}],
        idle=IdleLines(interval_min=30, interval_max=60,
                       lines={"default": ["hello"]}),
        behaviors=[Behavior(on="pet.petted", then=[{"say": "hi"}])],
        animations=[Animation(id="idle")],
    )
    save_card(str(d), card)
    loaded = load_card(str(d))
    assert loaded.id == card.id
    assert loaded.name == card.name
    assert loaded.system_prompt == card.system_prompt
    assert loaded.idle.lines == {"default": ["hello"]}
    assert loaded.behaviors[0].on == "pet.petted"
    assert [e.id for e in loaded.expressions] == ["default"]
    # 未知字段不保留(save_card 只写模型声明字段)
    assert loaded.format == ""


def test_save_card_set_format(tmp_path, monkeypatch):
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    d = tmp_path / "card"
    save_card(str(d), CharacterCard(id="card.fmt"), set_format=True)
    mf = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert mf["format"] == "chara-1"
    assert mf["type"] == "card"
    assert load_card(str(d)).format == "chara-1"


# ----------------------------------------------------------------------
# schema 漂移
# ----------------------------------------------------------------------

def test_schema_matches_build():
    from tools.export_chara_schema import build_schema
    schema_path = os.path.join(paths.BASE_DIR, "docs", "schema", "chara.schema.json")
    assert os.path.isfile(schema_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        disk = json.load(f)
    assert disk == build_schema()
