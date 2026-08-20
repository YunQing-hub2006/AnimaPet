# -*- coding: utf-8 -*-
"""utils 工具测试: jsonio 原子写与白名单路径校验 + theme 合并。"""
import json
import os

import pytest

from anima.utils import jsonio, paths, theme


def test_jsonio_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({os.path.normpath(paths.CONFIG_PATH)}))
    data = {"a": 1, "nested": {"k": "v"}}
    jsonio.save(paths.CONFIG_PATH, data)
    assert jsonio.load(paths.CONFIG_PATH, {}) == data


def test_jsonio_load_missing_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({os.path.normpath(paths.CONFIG_PATH)}))
    default = {"api": {"base_url": "default"}}
    assert jsonio.load(paths.CONFIG_PATH, default) == default


def test_jsonio_load_corrupt_returns_default(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("not json{{{", encoding="utf-8")
    monkeypatch.setattr(paths, "CONFIG_PATH", str(bad))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({os.path.normpath(str(bad))}))
    assert jsonio.load(paths.CONFIG_PATH, {"ok": True}) == {"ok": True}


def test_jsonio_load_dict_shallow_merge(tmp_path, monkeypatch):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"a": {"x": 1}, "b": 2}), encoding="utf-8")
    monkeypatch.setattr(paths, "CONFIG_PATH", str(f))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({os.path.normpath(str(f))}))
    result = jsonio.load(paths.CONFIG_PATH, {"a": {"y": 2}, "c": 3})
    assert result == {"a": {"x": 1, "y": 2}, "b": 2, "c": 3}


def test_jsonio_save_atomic_no_partial(tmp_path, monkeypatch):
    f = tmp_path / "atomic.json"
    monkeypatch.setattr(paths, "CONFIG_PATH", str(f))
    monkeypatch.setattr(jsonio, "_FILES", frozenset({os.path.normpath(str(f))}))
    jsonio.save(paths.CONFIG_PATH, {"v": 1})
    assert not (tmp_path / "atomic.json.tmp").exists()


def test_jsonio_rejects_traversal_outside_whitelist():
    with pytest.raises(ValueError):
        jsonio.save("../../../etc/evil.json", {"x": 1})


def test_jsonio_rejects_unknown_path(tmp_path):
    with pytest.raises(ValueError):
        jsonio.load(str(tmp_path / "random.json"), {})


def test_theme_merge_overrides_strings():
    t = theme.merge_theme({"accent": "#000000", "font_family": "KaiTi"})
    assert t["accent"] == "#000000"
    assert t["font_family"] == "KaiTi"


def test_theme_merge_ignores_non_string():
    t = theme.merge_theme({"font_size": "not-a-number-list", "accent": ""})
    assert t["accent"] == "#b04060"  # 空字符串被忽略
    assert t["font_size"] == theme.DEFAULT_THEME["font_size"]


def test_theme_merge_none_safe():
    assert theme.merge_theme(None) == dict(theme.DEFAULT_THEME)
