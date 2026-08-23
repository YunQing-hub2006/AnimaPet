# -*- coding: utf-8 -*-
"""导出 .chara 角色卡 JSON Schema(PLAN Phase 3 第 1 项)。

用法::

    python tools/export_chara_schema.py

固定输出到仓库内 ``docs/schema/chara.schema.json``(jsonio 原子写, 生成物
随仓库提交; tests/test_models.py 断言其与模型同步, 防漂移)。
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from anima.models import CharacterCard      # noqa: E402
from anima.utils import jsonio, paths       # noqa: E402


def build_schema() -> dict:
    schema = CharacterCard.model_json_schema()
    schema["title"] = "AnimaPet .chara Character Card"
    schema["$id"] = "https://animapet.local/schema/chara.schema.json"
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    return schema


def main() -> int:
    out = os.path.join(paths.BASE_DIR, "docs", "schema", "chara.schema.json")
    jsonio.save(out, build_schema())
    print("schema written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
