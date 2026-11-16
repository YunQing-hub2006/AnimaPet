"""验收脚本：统计 core 规模（物理行 + 代码行）并检查无第三方 import。

规模用两个口径（v1.2 起同时生效，与上游 Anima 内核仓库同步）：

- `raw`：物理行数，上限 1200。本内核 docstring 占比约五成，物理行数
  主要反映文档量，因此放得宽。
- `code`：去掉空行、注释行与 docstring 之后的代码行数，上限 650。这才是
  "内核保持小巧"的真正守门指标。

v1.2 之前只有 `raw < 1000` 一条。它作为代理指标在 docstring 变详细后
开始失真（841 行时其实只有 ~450 行代码），于是拆成上面两条：物理行数防止
文件无限膨胀，代码行数防止内核真的变胖。
"""

import ast
import pathlib
import sys

RAW_LIMIT = 1200
CODE_LIMIT = 650

core = pathlib.Path(__file__).resolve().parents[1] / "anima" / "core"


def _docstring_lines(tree: ast.AST) -> set[int]:
    """收集全部 docstring 占用的行号（模块/类/函数的首条字符串表达式）。"""
    marked: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            marked.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return marked


raw_total = 0
code_total = 0
for f in sorted(core.glob("*.py")):
    text = f.read_text(encoding="utf-8")
    lines = text.splitlines()
    doc_lines = _docstring_lines(ast.parse(text))
    code = sum(
        1
        for i, line in enumerate(lines, 1)
        if line.strip() and not line.strip().startswith("#") and i not in doc_lines
    )
    raw_total += len(lines)
    code_total += code
    print(f"{f.name:20s} raw={len(lines):4d}  code={code:4d}")

print(f"{'TOTAL':20s} raw={raw_total:4d}  code={code_total:4d}")
print(f"上限: raw < {RAW_LIMIT}, code < {CODE_LIMIT}")
assert raw_total < RAW_LIMIT, f"core 物理行数 {raw_total} 超过 {RAW_LIMIT}"
assert code_total < CODE_LIMIT, f"core 代码行数 {code_total} 超过 {CODE_LIMIT}"

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
