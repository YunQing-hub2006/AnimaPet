# -*- coding: utf-8 -*-
"""safe_eval 回归测试(自 YingPet 测试改写): 白名单语法 + 变量解析 + 永不崩溃。"""
import pytest

from anima.plugins import safe_eval
from anima.plugins.safe_eval import SafeEvalError, evaluate, evaluate_detailed


def test_basic_comparison():
    assert evaluate("time >= 23:00 or time < 05:00", {"time": 100}) is True   # 01:40
    assert evaluate("time >= 23:00 or time < 05:00", {"time": 23 * 60}) is True
    assert evaluate("time >= 23:00 or time < 05:00", {"time": 12 * 60}) is False


def test_state_and_event_paths():
    assert evaluate("state.affinity >= 20", {"state": {"affinity": 20}}) is True
    assert evaluate("state.affinity >= 20", {"state": {"affinity": 19}}) is False
    assert evaluate("event.affinity % 20 == 0", {"event": {"affinity": 40}}) is True
    assert evaluate("event.affinity % 20 == 0", {"event": {"affinity": 41}}) is False
    assert evaluate("state.a.b > 1", {"state": {"a": {"b": 2}}}) is True


def test_missing_path_is_false_not_crash():
    assert evaluate("state.nothing >= 20", {"state": {}}) is False
    assert evaluate("event.nope == 'x'", {}) is False


def test_weekday_and_rand():
    assert evaluate("weekday in [5, 6]", {"weekday": 6}) is True
    assert evaluate("weekday in [5, 6]", {"weekday": 2}) is False
    assert evaluate("rand < 0.5", {"rand": 0.2}) is True
    assert evaluate("rand < 0.5", {"rand": 0.8}) is False


def test_boolean_ops():
    ctx = {"event": {"ok": True, "emotion": "happy"}}
    assert evaluate("event.ok and event.emotion != 'default'", ctx) is True
    assert evaluate("event.ok and event.emotion == 'default'", ctx) is False
    assert evaluate("not event.ok", {"event": {"ok": False}}) is True
    assert evaluate("event.ok or event.bad", {"event": {"ok": False, "bad": True}}) is True


def test_list_and_in():
    assert evaluate("event.x in [1, 2, 3]", {"event": {"x": 2}}) is True
    assert evaluate("event.x in []", {"event": {"x": 2}}) is False
    assert evaluate("1 + 2 == 3") is True
    assert evaluate("5 - 2 == 3") is True
    assert evaluate("'a' + 'b' == 'ab'") is True


def test_parse_error_status():
    ok, status = evaluate_detailed("state.x > 1 and")
    assert ok is False
    assert status == "parse_error"
    ok, status = evaluate_detailed("state.x > 1 )")
    assert ok is False
    assert status == "parse_error"
    # 恶意代码一律解析失败, 绝不执行
    ok, status = evaluate_detailed("__import__('os').system('calc')")
    assert ok is False
    assert status == "parse_error"


def test_empty_condition_is_true():
    ok, status = evaluate_detailed("")
    assert ok is True and status == "ok"
    assert evaluate("   ") is True


def test_time_token_before_number():
    # 23:00 是时间不是除法: 23:00 → 1380 分钟
    assert evaluate("time >= 23:00", {"time": 1380}) is True


def test_tokenizer_error():
    with pytest.raises(SafeEvalError):
        safe_eval._tokenize("state.x $ 5")
