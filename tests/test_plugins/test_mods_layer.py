# -*- coding: utf-8 -*-
"""mods 数据层测试: 扫描、注册分流、zip 导入导出、zip-slip 防护。"""
import json
import os
import zipfile

import pytest

from anima.mods import loader, packer, registry


# ---------- fixtures ----------

@pytest.fixture
def mods_tree(tmp_path, monkeypatch):
    """构造一个含 card.ying + ui.default + feature.hello 的 mods/ 树。"""
    from anima.utils import jsonio, paths
    mods_dir = tmp_path / "mods"
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    # jsonio 的项目根校验必须与 MODS_DIR 重定向同步, 否则扫描临时目录会被拒
    monkeypatch.setattr(jsonio, "_BASE", os.path.normpath(str(tmp_path)))
    mods_dir.mkdir()

    (mods_dir / "card.ying").mkdir()
    (mods_dir / "card.ying" / "manifest.json").write_text(json.dumps({
        "id": "card.ying", "type": "card", "version": "1.0.0", "name": "影",
        "system_prompt": "测试人设", "idle_anim": "idle", "talk_anim": "talk",
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "card.ying" / "anims" / "idle" / "frames").mkdir(parents=True)
    (mods_dir / "card.ying" / "anims" / "talk" / "frames").mkdir(parents=True)
    (mods_dir / "card.ying" / "emotes.json").write_text(json.dumps({
        "emotes": {"default": {"name": "平时", "lines": ["你好"]}},
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "card.ying" / "idle.json").write_text(json.dumps({
        "interval_min": 30, "interval_max": 42,
        "lines": {"default": ["云梦泽"], "petted": ["别摸头"]},
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "card.ying" / "behaviors.json").write_text(json.dumps({
        "rules": [{"on": "pet.petted", "then": [{"say": "好感 {event.affinity}"}]}],
    }, ensure_ascii=False), encoding="utf-8")

    (mods_dir / "ui.default").mkdir()
    (mods_dir / "ui.default" / "manifest.json").write_text(json.dumps({
        "id": "ui.default", "type": "ui", "name": "默认", "theme": {"accent": "#b04060"},
    }, ensure_ascii=False), encoding="utf-8")

    (mods_dir / "feature.hello").mkdir()
    (mods_dir / "feature.hello" / "manifest.json").write_text(json.dumps({
        "id": "feature.hello", "type": "feature", "main": "plugin.py", "name": "你好",
    }, ensure_ascii=False), encoding="utf-8")
    (mods_dir / "feature.hello" / "plugin.py").write_text(
        "from anima.core import Plugin\nclass Hello(Plugin):\n    name = 'feature.hello'\n",
        encoding="utf-8")
    return mods_dir


# ---------- 扫描 ----------

def test_scan_mods_discovers_all_types(mods_tree):
    mods, errors = loader.scan_mods()
    assert errors == []
    ids = {m.id for m in mods}
    assert "card.ying" in ids
    assert "card.ying:idle" in ids          # 卡内动画
    assert "card.ying:talk" in ids
    assert "card.ying:idle" in ids or "default" in ids
    # 表情
    emotes = [m for m in mods if isinstance(m, loader.EmoteDef)]
    assert any(e.id == "default" and e.character == "card.ying" for e in emotes)
    # 台词包
    idles = [m for m in mods if isinstance(m, loader.IdlePack)]
    assert idles and idles[0].sections.get("petted") == ["别摸头"]
    # 行为
    behs = [m for m in mods if isinstance(m, loader.BehaviorMod)]
    assert behs and behs[0].rules[0]["on"] == "pet.petted"
    # 皮肤/功能
    assert any(isinstance(m, loader.UiMod) and m.id == "ui.default" for m in mods)
    assert any(isinstance(m, loader.FeatureMod) and m.id == "feature.hello" for m in mods)


def test_scan_mods_corrupt_manifest_reports_error(mods_tree):
    (mods_tree / "card.ying" / "manifest.json").write_text("not json{{{", encoding="utf-8")
    mods, errors = loader.scan_mods()
    assert errors, "坏 manifest 应进入 errors"
    assert any("card.ying" in name for name, _ in errors)


def test_scan_mods_bad_type_reports_error(mods_tree):
    (mods_tree / "card.ying" / "manifest.json").write_text(json.dumps({
        "id": "x", "type": "bogus"}), encoding="utf-8")
    mods, errors = loader.scan_mods()
    assert errors


# ---------- registry 分流 ----------

def test_registry_apply_enabled_filter(mods_tree):
    mods, errors = loader.scan_mods()
    reg = registry.Registry()
    enabled = {"card.ying": True, "ui.default": False}  # feature.hello 缺省启用
    reg.apply(mods, enabled, errors)
    assert reg.characters.get("card.ying")
    assert reg.uis.get("ui.default") is None       # 禁用: 加载但不收纳
    assert reg.features.get("feature.hello")       # 缺省 True
    # all_mods 永远收全量(供管理面板显示)
    all_ids = {m.id for m in reg.all_mods}
    assert "ui.default" in all_ids


def test_registry_character_queries(mods_tree):
    mods, errors = loader.scan_mods()
    reg = registry.Registry()
    reg.apply(mods)
    reg.active_char_id = "card.ying"
    assert reg.character("card.ying").system_prompt == "测试人设"
    # 表情归属
    emotes = reg.character_emotes("card.ying")
    assert "default" in emotes
    # 行为
    behs = reg.character_behaviors("card.ying")
    assert "card.ying:behaviors" in behs
    # 台词
    idle = reg.character_idle("card.ying")
    assert idle.id == "card.ying:idle"
    assert reg.idle_interval("card.ying") == (30, 42)
    assert reg.idle_line("card.ying:idle", "default") == "云梦泽"
    # 皮肤
    ui = reg.ui("ui.default")
    assert ui.id == "ui.default"


# ---------- packer ----------

def _make_zip(zip_path, entries):
    """entries: {内部路径: 内容字节}。"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)


def test_packer_roundtrip_export_import(mods_tree, tmp_path):
    zip_path = tmp_path / "hello.zip"
    mod_dir = mods_tree / "feature.hello"
    count = packer.export_mod(str(mod_dir), str(zip_path))
    assert count >= 2  # manifest + plugin.py
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any(n.startswith("feature.hello/") for n in names)

    new_id, dest = packer.import_mod_zip(str(zip_path), str(mods_tree))
    assert new_id == "feature.hello_2"  # 原目录已存在 → 冲突改名
    assert os.path.isdir(dest)
    mf = json.loads((mods_tree / "feature.hello_2" / "manifest.json").read_text(encoding="utf-8"))
    assert mf["id"] == "feature.hello_2"  # 改名回写 manifest


def test_packer_import_rejects_zip_slip(mods_tree, tmp_path):
    evil = tmp_path / "evil.zip"
    _make_zip(evil, {"../evil.txt": b"pwned", "mod/manifest.json": json.dumps({
        "id": "mod", "type": "ui"}).encode()})
    with pytest.raises(ValueError):
        packer.import_mod_zip(str(evil), str(mods_tree))
    assert not (mods_tree.parent / "evil.txt").exists()


def test_packer_import_rejects_absolute_and_drive(tmp_path, mods_tree):
    bad = tmp_path / "abs.zip"
    _make_zip(bad, {"/etc/passwd": b"x"})
    with pytest.raises(ValueError):
        packer.import_mod_zip(str(bad), str(mods_tree))
    win = tmp_path / "win.zip"
    _make_zip(win, {"C:/Windows/evil": b"x"})
    with pytest.raises(ValueError):
        packer.import_mod_zip(str(win), str(mods_tree))


def test_packer_import_rejects_no_manifest(tmp_path, mods_tree):
    bad = tmp_path / "no-manifest.zip"
    _make_zip(bad, {"foo.txt": b"hi"})
    with pytest.raises(ValueError):
        packer.import_mod_zip(str(bad), str(mods_tree))


def test_packer_import_rejects_bad_id(tmp_path, mods_tree):
    bad = tmp_path / "badid.zip"
    _make_zip(bad, {"m/manifest.json": json.dumps({
        "id": "has space!!", "type": "ui"}).encode()})
    with pytest.raises(ValueError):
        packer.import_mod_zip(str(bad), str(mods_tree))


def test_packer_import_flat_layout_no_topdir(tmp_path, mods_tree):
    # 平铺布局: manifest.json 在根部
    flat = tmp_path / "flat.zip"
    _make_zip(flat, {"manifest.json": json.dumps({
        "id": "ui.flat", "type": "ui", "name": "平铺"}).encode()})
    new_id, dest = packer.import_mod_zip(str(flat), str(mods_tree))
    assert new_id == "ui.flat"
    assert os.path.isfile(os.path.join(dest, "manifest.json"))


def test_packer_export_skips_junk(tmp_path):
    mod_dir = tmp_path / "m"
    (mod_dir / "__pycache__").mkdir(parents=True)
    (mod_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (mod_dir / "__pycache__" / "x.pyc").write_bytes(b"x")
    (mod_dir / "keep.py").write_text("", encoding="utf-8")
    dest = tmp_path / "m.zip"
    packer.export_mod(str(mod_dir), str(dest))
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    assert any(n.endswith("keep.py") for n in names)


# ---------- Phase 3: card 子文件逐文件降级 ----------

def test_card_bad_subfiles_degrades_isolated(mods_tree):
    (mods_tree / "card.ying" / "emotes.json").write_text(json.dumps({
        "emotes": {
            "good": {"name": "好", "lines": ["ok"]},
            "bad": [1, 2, 3],
        }
    }, ensure_ascii=False), encoding="utf-8")
    (mods_tree / "card.ying" / "idle.json").write_text(json.dumps({
        "interval_min": "abc", "interval_max": None,
        "lines": {"default": ["幸存台词"]},
    }, ensure_ascii=False), encoding="utf-8")
    (mods_tree / "card.ying" / "behaviors.json").write_text(json.dumps({
        "rules": [
            {"on": "", "then": []},
            {"on": "pet.petted", "then": [{"say": "好规则"}]},
        ]
    }, ensure_ascii=False), encoding="utf-8")

    mods, errors = loader.scan_mods()
    assert errors == []
    emotes = [m for m in mods if isinstance(m, loader.EmoteDef)]
    assert len(emotes) == 1 and emotes[0].id == "good"          # 坏项丢弃, 好项保留
    idles = [m for m in mods if isinstance(m, loader.IdlePack)]
    assert idles and idles[0].interval_min == 180 and idles[0].interval_max == 420
    behs = [m for m in mods if isinstance(m, loader.BehaviorMod)]
    assert behs and len(behs[0].rules) == 1
    assert behs[0].rules[0]["on"] == "pet.petted"
    # registry.errors 为空(逐文件降级 = 不整卡报错)
    from anima.mods.registry import Registry
    reg = Registry()
    reg.apply(mods)
    assert reg.errors == []


# ---------- Phase 3: .chara 类型/id 归一 ----------

def test_normalize_chara_id():
    assert packer._normalize_chara_id("mio") == "card.mio"
    assert packer._normalize_chara_id("card.mio") == "card.mio"
    assert packer._normalize_chara_id("ying.chara") == "card.ying.chara"
    assert packer._normalize_chara_id("!!bad!!") == "card.bad"


def test_packer_import_chara_normalizes_type_and_id(mods_tree, tmp_path):
    zip_path = tmp_path / "mio.chara.zip"
    _make_zip(zip_path, {
        "mio/manifest.json": json.dumps({
            "id": "ying.mio", "type": "chara", "version": "1.0.0", "name": "米奥",
        }).encode(),
        "mio/emotes.json": json.dumps({"emotes": {"default": {"name": "平时"}}}).encode(),
    })
    new_id, dest = packer.import_mod_zip(str(zip_path), str(mods_tree))
    assert new_id == "card.ying.mio"
    assert os.path.basename(dest) == "card.ying.mio"
    mf = json.loads(open(os.path.join(dest, "manifest.json"), encoding="utf-8").read())
    assert mf["type"] == "card"            # chara -> card 归一
    assert mf["id"] == "card.ying.mio"     # 前缀归一
    # 重扫后注册表按 card 归类
    mods, errors = loader.scan_mods()
    assert errors == []
    assert any(isinstance(m, loader.CharacterMod) and m.id == "card.ying.mio" for m in mods)

