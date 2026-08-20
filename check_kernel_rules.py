"""验收脚本：统计 core 行数并检查无第三方 import（原样继承 Anima-v1.1 内核仓库）。"""

import ast
import pathlib
import sys

core = pathlib.Path(__file__).parent / "anima" / "core"
total = 0
for f in sorted(core.glob("*.py")):
    lines = len(f.read_text(encoding="utf-8").splitlines())
    total += lines
    print(f"{f.name:20s} {lines}")
print(f"{'TOTAL':20s} {total}  (<1000 目标)")
assert total < 1000, f"core 总行数 {total} 超过 1000"

stdlib = set(sys.stdlib_module_names)
for f in core.glob("*.py"):
    tree = ast.parse(f.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                assert root in stdlib or root == "anima", f"{f}: 第三方 import {a.name}"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            assert root in stdlib or root == "anima", f"{f}: 第三方 import {node.module}"
print("import 检查: 全部为标准库 / anima 自身")
