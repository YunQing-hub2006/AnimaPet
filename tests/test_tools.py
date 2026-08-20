# -*- coding: utf-8 -*-
"""迁移工具测试: config 合并补字段 / state 平移 / chat_history 复制 / 备份 / 只读源 / dry-run。"""
import json
import os

import pytest

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
