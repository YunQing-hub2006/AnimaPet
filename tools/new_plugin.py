# -*- coding: utf-8 -*-
"""新建功能模组脚手架(PLAN Phase 5): python tools/new_plugin.py <短名> <名称>

生成 mods/feature.<短名>/manifest.json + plugin.py(Hello World 模板)。
"""
import argparse
import os
import re
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from anima.utils import jsonio, paths  # noqa: E402

_ID_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")

TEMPLATE = '''# -*- coding: utf-8 -*-
"""{name} —— AnimaPet 功能模组。

契约: 定义 class Feature; on_load 里用白名单 ctx 注册菜单/监听事件;
on_disable 里停线程/计时器。改完菜单"重新扫描"即热生效。
"""


class Feature:
    id = "{mod_id}"
    name = "{name}"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("{name}", self._hello)
        ctx.log("已加载")

    def _hello(self):
        self.ctx.say("你好, 我是功能模组 {name}。")

    def on_disable(self):
        pass
'''


def create_plugin(short_id, name):
    """创建 feature.<short_id> 文件夹, 返回 mod_id。"""
    base = str(short_id or "").strip().lower()
    if base.startswith("feature."):
        base = base[len("feature."):]
    if not _ID_RE.fullmatch(base or ""):
        raise ValueError("模组 id 不合法(小写字母/数字/_.-): %r" % short_id)
    mod_id = "feature." + base
    target = os.path.join(paths.MODS_DIR, mod_id)
    if os.path.exists(target):
        raise ValueError("模组已存在: %s" % mod_id)
    os.makedirs(target, exist_ok=True)
    jsonio.save(os.path.join(target, "manifest.json"), {
        "id": mod_id, "type": "feature", "version": "1.0.0",
        "name": str(name or base), "main": "plugin.py",
        "description": "new_plugin.py 生成的功能模组模板",
    })
    with open(os.path.join(target, "plugin.py"), "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(mod_id=mod_id, name=str(name or base)))
    return mod_id


def main(argv=None):
    parser = argparse.ArgumentParser(description="新建 feature 功能模组")
    parser.add_argument("short_id", help="模组短名(如 greet, 自动补 feature.)")
    parser.add_argument("name", nargs="?", help="显示名(默认 = 短名)")
    args = parser.parse_args(argv)
    try:
        mod_id = create_plugin(args.short_id, args.name or args.short_id)
    except ValueError as e:
        print("[ERROR] %s" % e)
        return 2
    print("已创建: %s -> %s" % (mod_id, os.path.join(paths.MODS_DIR, mod_id)))
    print("下一步: 打开「模组管理」→ 重新扫描, 或重启应用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())