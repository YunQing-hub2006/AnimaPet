# -*- coding: utf-8 -*-
"""安全条件求值器 —— 行为规则 when/if 条件专用。

设计约束:
1. 绝不使用 eval/exec —— 模组无法通过条件表达式执行任意代码
2. 语法白名单: 比较 / 布尔 / 取模 / 加减 / in / 取值
3. 变量白名单: time(当日分钟数) weekday(0-6) rand(0..1) state.* event.*

语法示例:
    time >= 23:00 or time < 05:00
    state.affinity >= 20 and weekday in [5, 6]
    event.affinity % 20 == 0
    rand < 0.5
解析失败一律返回 False 并记日志(规则不触发), 绝不让坏表达式拖垮程序。

(自 YingPet-v4 core/safe_eval.py 原样搬运, 仅改 import 路径。)
"""
import random
import re

from anima.utils import log

_log = log.get("safe_eval")


class SafeEvalError(Exception):
    pass


# 注意: time(23:00) 必须排在 number 之前, 否则 23:00 会被拆成 23 和坏字符 ':'
_TOKEN_RE = re.compile(r"""
    \s*(?:
        (?P<time>\d{1,2}:\d{2})
      | (?P<number>\d+(?:\.\d+)?)
      | (?P<string>"[^"]*"|'[^']*')
      | (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
      | (?P<op>==|!=|>=|<=|>|<|%|\+|-)
      | (?P<par>[()\[\],])
    )
""", re.VERBOSE)


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            rest = text[pos:].strip()
            if rest:
                raise SafeEvalError("无法识别的字符: %r" % rest[:12])
            break
        kind = m.lastgroup
        val = m.group(kind)  # 只取捕获组内容, 排除前导空白
        if kind == "time":
            h, mi = val.split(":")
            tokens.append(("num", int(h) * 60 + int(mi)))
        elif kind == "number":
            tokens.append(("num", float(val) if "." in val else int(val)))
        elif kind == "string":
            tokens.append(("str", val[1:-1]))
        elif kind == "name":
            tokens.append(("name", val))
        elif kind == "op":
            tokens.append(("op", val))
        else:
            tokens.append(("par", val))
        pos = m.end()
    return tokens


def _truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        t = self._peek()
        if t is not None:
            self.pos += 1
        return t

    def _expect(self, kind, val=None):
        t = self._next()
        if t is None or t[0] != kind or (val is not None and t[1] != val):
            raise SafeEvalError("语法错误: 期望 %s, 实际 %r" % (val or kind, t))
        return t

    def parse(self, ctx):
        v = self._parse_or(ctx)
        if self._peek() is not None:
            raise SafeEvalError("存在多余内容: %r" % (self._peek(),))
        return v

    # 优先级: or < and < not < 二元运算 < 原子
    def _parse_or(self, ctx):
        v = self._parse_and(ctx)
        while self._peek() == ("name", "or"):
            self._next()
            rhs = self._parse_and(ctx)   # 必须先解析完, 不能短路跳过
            v = _truthy(v) or _truthy(rhs)
        return v

    def _parse_and(self, ctx):
        v = self._parse_not(ctx)
        while self._peek() == ("name", "and"):
            self._next()
            rhs = self._parse_not(ctx)   # 同上, 不能短路跳过
            v = _truthy(v) and _truthy(rhs)
        return v

    def _parse_not(self, ctx):
        if self._peek() == ("name", "not"):
            self._next()
            return not _truthy(self._parse_not(ctx))
        return self._parse_binary(ctx)

    def _parse_binary(self, ctx):
        left = self._parse_primary(ctx)
        while True:
            t = self._peek()
            if t is not None and t == ("name", "in"):
                self._next()
                left = self._apply("in", left, self._parse_primary(ctx))
                continue
            if t is None or t[0] != "op":
                break
            self._next()
            left = self._apply(t[1], left, self._parse_primary(ctx))
        return left

    def _parse_primary(self, ctx):
        t = self._next()
        if t is None:
            raise SafeEvalError("表达式不完整")
        kind, val = t
        if kind in ("num", "str"):
            return val
        if kind == "name":
            return self._resolve_name(val, ctx)
        if kind == "par" and val == "(":
            v = self._parse_or(ctx)
            self._expect("par", ")")
            return v
        if kind == "par" and val == "[":
            items = []
            if self._peek() == ("par", "]"):
                self._next()
                return items
            while True:
                items.append(self._parse_binary(ctx))
                nxt = self._next()
                if nxt == ("par", "]"):
                    break
                if nxt != ("par", ","):
                    raise SafeEvalError("列表语法错误")
            return items
        raise SafeEvalError("意外的符号: %r" % ((kind, val),))

    @staticmethod
    def _apply(op, left, right):
        try:
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == ">=":
                return left >= right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == "in":
                return left in right
            if op == "%":
                return left % right
            if op == "+":
                return left + right
            if op == "-":
                return left - right
        except Exception:
            return False
        raise SafeEvalError("不支持的运算符: %s" % op)

    @staticmethod
    def _resolve_name(name, ctx):
        if name in ("time", "weekday", "rand"):
            return ctx.get(name)
        parts = name.split(".")
        if len(parts) >= 2 and parts[0] in ("state", "event", "config"):
            cur = ctx.get(parts[0])
            for p in parts[1:]:
                if not isinstance(cur, dict) or p not in cur:
                    return None
                cur = cur[p]
            return cur
        _log.warning("safe_eval: 未识别的变量 %r, 按 None 处理", name)
        return None


def _now_minutes():
    import time as _t
    lt = _t.localtime()
    return lt.tm_hour * 60 + lt.tm_min


def _now_weekday():
    import time as _t
    return _t.localtime().tm_wday


def evaluate_detailed(expr, context=None):
    """求值条件表达式, 返回 (结果, 状态)。

    context: {"state": {...}, "event": {...}} (time/weekday/rand 自动注入,
    测试时可在 context 里显式传 time 等以固定结果)。
    状态: "ok" 正常求值 | "parse_error" 语法错误/非法写法。
    """
    ctx = dict(context or {})
    ctx.setdefault("time", _now_minutes())
    ctx.setdefault("weekday", _now_weekday())
    ctx.setdefault("rand", random.random())
    try:
        tokens = _tokenize(str(expr))
        if not tokens:
            return True, "ok"  # 空条件 = 不设限
        return _truthy(_Parser(tokens).parse(ctx)), "ok"
    except SafeEvalError as e:
        _log.warning("条件表达式无效 %r: %s", expr, e)
        return False, "parse_error"


def evaluate(expr, context=None):
    """求值条件表达式, 返回布尔结果(兼容旧接口, B7 新增 evaluate_detailed)。"""
    return evaluate_detailed(expr, context)[0]
