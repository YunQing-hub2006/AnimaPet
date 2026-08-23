# -*- coding: utf-8 -*-
"""迁移工具测试: config 合并补字段 / state 平移 / chat_history 复制 / 备份 / 只读源 / dry-run。"""
import json
import os
import shutil
import zipfile

import pytest

from anima.mods import loader
from anima.models import load_card
from anima.utils import jsonio, paths
from tools import migrate_yingpet as mig


@pytest.fixture
def yingpet_dir(tmp_path):
    """伪造 YingPet-v4 源目录: 根目录平铺 config/state/chat_history。"""
    src = tmp_path / "YingPet-v4"
    src.mkdir()
    (src / "config.json").write_text(json.dumps({
        "api": {"base_url": "https://old.example.com", "api_key": "oldkey"},
        "window": {"size": "large"},
        "custom_section": {"x": 1},
    }, ensure_ascii=False), encoding="utf-8")
    (src / "state.json").write_text(json.dumps({
        "affinity": 42, "conv_id": 7, "todo.items": [{"text": "买猫粮", "done": False}],
    }, ensure_ascii=False), encoding="utf-8")
    (src / "chat_history.json").write_text(json.dumps([{"role": "user", "content": "hi"}]))
    return src


def test_migrate_full_and_backup(yingpet_dir, tmp_path):
    data = tmp_path / "data"
    # 预置既有文件 → 应触发备份
    data.mkdir()
    (data / "config.json").write_text('{"api": {"api_key": "existing"}}', encoding="utf-8")
    (data / "state.json").write_text('{"affinity": 1}', encoding="utf-8")

    report = mig.migrate(str(yingpet_dir), str(data))
    assert report["backups"], report          # 两个既有文件都备份了
    assert len(report["writes"]) == 3

    cfg = json.loads((data / "config.json").read_text(encoding="utf-8"))
    assert cfg["api"]["base_url"] == "https://old.example.com"   # 源值覆盖默认
    assert cfg["api"]["model"] == "deepseek-v4-flash"            # 默认补齐
    assert cfg["window"]["size"] == "large"
    assert cfg["window"]["sit_reminder"] is True                 # 缺失子键补齐
    assert cfg["_legacy"] == {"custom_section": {"x": 1}}        # 未知键保留

    st = json.loads((data / "state.json").read_text(encoding="utf-8"))
    assert st["affinity"] == 42
    assert st["petted_count"] == 0                                # 默认补齐
    assert st["todo.items"][0]["text"] == "买猫粮"                # 功能模组状态平移
    assert st["conv_id"] == 7

    hist = data / "chat_history" / "yingpet_v4.json"
    assert hist.exists()
    assert json.loads(hist.read_text(encoding="utf-8"))[0]["role"] == "user"

    # 源目录只读: 内容与迁移前一致
    assert json.loads((yingpet_dir / "config.json").read_text(encoding="utf-8"))["api"]["api_key"] == "oldkey"


def test_migrate_dry_run_writes_nothing(yingpet_dir, tmp_path):
    data = tmp_path / "data"
    report = mig.migrate(str(yingpet_dir), str(data), dry_run=True)
    assert len(report["writes"]) == 3
    assert not (data / "config.json").exists()
    assert not (data / "state.json").exists()
    assert not (data / "chat_history").exists()
    assert report["backups"] == []


def test_migrate_missing_source_reports_skip(tmp_path):
    report = mig.migrate(str(tmp_path / "nope"), str(tmp_path / "data"))
    assert report["writes"] == []
    assert report["skipped"]


def test_migrate_missing_files_partial(yingpet_dir, tmp_path):
    (yingpet_dir / "state.json").unlink()
    (yingpet_dir / "chat_history.json").unlink()
    report = mig.migrate(str(yingpet_dir), str(tmp_path / "data"))
    assert [k for k, _ in report["writes"]] == ["config"]        # 只迁存在的文件


def test_migrate_chat_history_split_by_character(yingpet_dir, tmp_path):
    """源 config 声明当前角色 → 历史同时落到 characters/<id>/ 与全局留档。"""
    cfg = json.loads((yingpet_dir / "config.json").read_text(encoding="utf-8"))
    cfg.setdefault("mods", {})["character"] = "card.ying"
    (yingpet_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False),
                                             encoding="utf-8")
    data = tmp_path / "data"
    report = mig.migrate(str(yingpet_dir), str(data))
    assert any(k == "chat_history[card.ying]" for k, _ in report["writes"])
    assert (data / "characters" / "card.ying" / "chat_history.json").exists()
    assert (data / "chat_history" / "yingpet_v4.json").exists()
    assert json.loads((data / "characters" / "card.ying" / "chat_history.json")
                      .read_text(encoding="utf-8"))[0]["role"] == "user"


# ----------------------------------------------------------------------
# .chara 导出 / 导入
# ----------------------------------------------------------------------

def test_export_chara_roundtrip(tmp_path, monkeypatch):
    """真实 card.ying → .chara zip → 解包 load_card 一致 + format=chara-1。"""
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    src = os.path.join(paths.MODS_DIR, "card.ying")
    card_dir = tmp_path / "card.ying"
    shutil.copytree(src, card_dir)
    zip_path = tmp_path / "ying.chara.zip"
    new_id, n = mig.export_chara(str(card_dir), str(zip_path))
    assert new_id == "card.ying"
    assert n > 0
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        mf = json.loads(zf.read(zf.namelist()[0].split("/")[0] + "/manifest.json").decode("utf-8"))
    assert mf["format"] == "chara-1"
    out = tmp_path / "extract"
    out.mkdir()
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out)
    top = next(p for p in out.iterdir() if p.is_dir())
    card = load_card(str(top))
    assert card.id == "card.ying"
    assert card.format == "chara-1"
    assert len(card.expressions) >= 5
    assert "angry" in [a.id for a in card.animations]


def test_export_chara_bad_card_no_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({"type": "card"}), encoding="utf-8")
    zip_path = tmp_path / "bad.chara.zip"
    with pytest.raises(ValueError):
        mig.export_chara(str(bad), str(zip_path))
    assert not zip_path.exists()          # 坏卡不产出半成品包


def test_import_chara_installs_and_validates(tmp_path, monkeypatch):
    monkeypatch.setattr(jsonio, "_BASE", str(tmp_path))
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    monkeypatch.setattr(paths, "MODS_DIR", str(mods_dir))
    # 手工构造一个 chara 类型包(packer 会归一为 card)
    z = tmp_path / "mio.chara.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("mio/manifest.json", json.dumps({
            "id": "ying.mio", "type": "chara", "version": "1.0.0", "name": "米奥",
            "system_prompt": "测试人设"}).encode("utf-8"))
        zf.writestr("mio/emotes.json", json.dumps({
            "emotes": {"default": {"name": "平时", "lines": ["hi"]}}}).encode("utf-8"))
    new_id, dest = mig.import_chara(str(z), mods_dir=str(mods_dir))
    assert new_id == "card.ying.mio"
    assert loader.scan_mods()[1] == []
    assert load_card(dest).id == "card.ying.mio"

