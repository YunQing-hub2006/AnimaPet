# -*- coding: utf-8 -*-
"""JSON read/write with atomic save and path whitelist guard."""
import json, os
from . import paths
from . import log
_log = log.get("jsonio")

class PathGuardError(ValueError):
    """Path rejected by jsonio whitelist guard."""

_BASE = os.path.normpath(paths.BASE_DIR)
_DOTDOT = chr(46)+chr(46)
def _copy_defaults(d):
    """递归复制默认值: 合并产物与模块级默认(如 DEFAULT_CONFIG)彻底解耦,
    防止运行时点路径写入污染后续 load 的默认值。"""
    out = {}
    for k, v in d.items():
        out[k] = _copy_defaults(v) if isinstance(v, dict) else v
    return out
def _guard(path):
    norm = str(path).replace(chr(92),"/")
    if _DOTDOT in norm.split("/"):
        raise PathGuardError("jsonio: traversal rejected")
    p = os.path.normpath(os.path.abspath(path))
    if p != _BASE and not p.startswith(_BASE + os.sep):
        raise PathGuardError("jsonio: outside project root")
    return p
def load(path, default):
    try:
        p = _guard(path)
    except PathGuardError:
        raise
    try:
        with open(p,"r",encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(default,dict) and isinstance(data,dict):
            merged = _copy_defaults(default)
            for k,v in data.items():
                if k in merged and isinstance(merged[k],dict) and isinstance(v,dict):
                    merged[k].update(v)
                else:
                    merged[k]=v
            return merged
        return data
    except Exception as e:
        _log.warning("load_json %s failed: %s",path,e)
        return _copy_defaults(default) if isinstance(default,dict) else default
def save(path, data):
    try:
        p=_guard(path)
    except PathGuardError:
        raise
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
        os.replace(tmp,p)
    except Exception as e:
        _log.warning("save_json %s failed: %s",path,e)
