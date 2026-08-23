# -*- coding: utf-8 -*-
"""YingPet-v4 数据一次性迁移工具: config/state/chat_history 平移 + 字段补齐
+ 角色卡 .chara 导入导出(Phase 3)。

用法::

    python tools/migrate_yingpet.py [--source E:\\dsh-work\\YingPet-v4] [--dry-run]
    python tools/migrate_yingpet.py --export-chara card.ying --out E:\\ying.chara.zip
    python tools/migrate_yingpet.py --import-chara E:\\mio.chara.zip [--activate]

原则(PLAN §六 风险对策):
- 源目录**只读**, 绝不改动 YingPet 任何文件;
- 目标 data/ 的既有文件写前备份到 ``data/backup/<时间戳>/``(只增不改);
- 字段补齐: 与 AnimaPet 默认结构合并, 未知键原样保留(功能模组状态如
  todo.items/clock.enabled 也随 state 平移, 功能对等不断档);
- chat_history.json 按角色分目录: 当前角色(config.mods.character)的历史
  落 ``data/characters/<id>/chat_history.json``, 其余角色历史留
  ``data/chat_history/yingpet_v4.json`` 待 Phase 4 分流(多角色历史无法
  从单一文件切分, 只迁当前角色是保守正确的);
- .chara 包 = zip(packim 防护) + manifest(format=chara-1) + Pydantic
  整体校验(load_card), 坏卡在导出时即报错, 不产出半成品包。
"""
import argparse
import json
import os
import shutil
import sys
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from anima.models import load_card                    # noqa: E402
from anima.mods import packer                         # noqa: E402
from anima.plugins.config import DEFAULT_CONFIG       # noqa: E402
from anima.plugins.state import DEFAULT_STATE         # noqa: E402
from anima.utils import paths                         # noqa: E402

#: YingPet-v4 的文件布局(源码运行): 数据文件在项目根, 不在 data/ 子目录。
YINGPET_FILES = {
    "config.json": "config.json",
    "state.json": "state.json",
    "chat_history.json": "chat_history.json",
}


def _load_json(path, default):
    """普通读(迁移源在项目根外, 不走 jsonio 守卫); 缺失/坏文件返回 default。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (ValueError, OSError):
        return None


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _backup(target_file, backup_dir):
    """目标文件已存在则先备份; 返回备份路径或 None。"""
    if not os.path.isfile(target_file):
        return None
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, os.path.basename(target_file))
    shutil.copy2(target_file, dest)
    return dest


def _merge_config(source_cfg):
    """YingPet config → AnimaPet 结构: 已知分层合并, 未知键保留进 _legacy。"""
    src = source_cfg or {}
    merged = {}
    for key, default in DEFAULT_CONFIG.items():
        if isinstance(default, dict):
            merged[key] = {**default, **{k: v for k, v in src.get(key, {}).items()
                                         if isinstance(src.get(key), dict)}}
        else:
            merged[key] = src.get(key, default)
    extra = {k: v for k, v in src.items() if k not in DEFAULT_CONFIG}
    if extra:
        merged["_legacy"] = extra
    return merged


def _merge_state(source_state):
    """YingPet state → AnimaPet: 补齐默认键, 其余(含功能模组状态)原样保留。"""
    merged = dict(DEFAULT_STATE)
    for k, v in (source_state or {}).items():
        merged[k] = v
    return merged


def _current_char_id(src_cfg):
    """源 config 里声明的当前角色 id(没有/不合法返回 "")。"""
    cid = str((src_cfg or {}).get("mods", {}).get("character", "") or "")
    return cid if cid else ""


def migrate(source_dir, target_data_dir, dry_run=False):
    """执行迁移。返回报告 dict; 源目录只读。"""
    report = {"source": str(source_dir), "backups": [], "writes": [], "skipped": []}
    backup_dir = os.path.join(target_data_dir, "backup", time.strftime("%Y%m%d-%H%M%S"))

    src_cfg = _load_json(os.path.join(source_dir, YINGPET_FILES["config.json"]), {})
    src_state = _load_json(os.path.join(source_dir, YINGPET_FILES["state.json"]), {})
    src_history = os.path.join(source_dir, YINGPET_FILES["chat_history.json"])

    plans = []
    if src_cfg is not None:
        plans.append(("config", os.path.join(target_data_dir, "config.json"),
                      _merge_config(src_cfg)))
    if src_state is not None:
        plans.append(("state", os.path.join(target_data_dir, "state.json"),
                      _merge_state(src_state)))
    if os.path.isfile(src_history):
        # 当前角色历史按角色分目录(Phase 3 隔离); 其余角色留全局待 Phase 4 分流
        cid = _current_char_id(src_cfg)
        if cid:
            plans.append(("chat_history[%s]" % cid,
                          os.path.join(target_data_dir, "characters", cid, "chat_history.json"),
                          "copy:" + src_history))
            plans.append(("chat_history", os.path.join(target_data_dir, "chat_history",
                                                       "yingpet_v4.json"),
                          "copy:" + src_history))
        else:
            plans.append(("chat_history",
                          os.path.join(target_data_dir, "chat_history", "yingpet_v4.json"),
                          "copy:" + src_history))

    for kind, target, payload in plans:
        if dry_run:
            report["writes"].append((kind, target))
            continue
        if kind.startswith("chat_history"):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src_history, target)
        else:
            b = _backup(target, backup_dir)
            if b:
                report["backups"].append(b)
            _atomic_write(target, payload)
        report["writes"].append((kind, target))

    if not src_cfg and not src_state and not os.path.isfile(src_history):
        report["skipped"].append("源目录里没有可迁移的数据文件: %s" % source_dir)
    return report


# ----------------------------------------------------------------------
# .chara 导入导出(Phase 3)
# ----------------------------------------------------------------------

def export_chara(card_dir, out_zip):
    """角色卡文件夹 -> .chara zip(先 Pydantic 整体校验再打包)。

    校验失败抛 ValueError(不产出半成品包); 输出带顶层目录 + format=chara-1
    标记(规范化的 .chara 形态)。返回 (new_id, 条目数)。
    """
    from anima.models import save_card
    card = load_card(card_dir)                    # 整体校验, 坏卡抛 ValueError
    card = card.model_copy(update={"format": "chara-1"})
    stage = os.path.join(os.path.dirname(os.path.abspath(out_zip)),
                         ".chara_stage_" + card.id.replace(":", "_"))
    shutil.rmtree(stage, ignore_errors=True)
    try:
        os.makedirs(stage, exist_ok=True)
        save_card(stage, card, set_format=True)
        # 帧目录/图片目录原样带走(保存的 manifest 只含声明字段, 素材靠复制)
        for sub in ("anims", "images"):
            src = os.path.join(card_dir, sub)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(stage, sub))
        if os.path.isfile(out_zip):
            os.remove(out_zip)
        n = packer.export_mod(stage, out_zip)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return card.id, n


def import_chara(zip_path, mods_dir=None, activate=False):
    """安装 .chara zip 到 mods/(packer 防护 + id/类型归一 + 装后整体校验)。

    返回 (new_id, dest)。activate=True 时把 config.mods.character 指向新卡
    (需 AnimaPet config 存在; 供 CLI --activate)。
    """
    mods_dir = mods_dir or paths.MODS_DIR
    new_id, dest = packer.import_mod_zip(zip_path, mods_dir)
    try:
        load_card(dest)                 # 装后再整体校验一遍(坏包明确报错)
    except ValueError:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    if activate:
        from anima.plugins.config import ConfigService
        cfg = ConfigService()
        cfg.load()
        cfg.set("mods.character", new_id)
        cfg.save()
    return new_id, dest


def main(argv=None):
    parser = argparse.ArgumentParser(description="YingPet-v4 -> AnimaPet 数据迁移 / .chara 角色卡包工具")
    sub = parser.add_subparsers(dest="cmd")

    p_mig = sub.add_parser("migrate", help="config/state/chat_history 平移(默认)")
    p_mig.add_argument("--source", default=r"E:\dsh-work\YingPet-v4",
                       help="YingPet-v4 目录(只读), 默认 E:\\dsh-work\\YingPet-v4")
    p_mig.add_argument("--dry-run", action="store_true", help="只打印计划, 不写文件")

    p_exp = sub.add_parser("export-chara", help="card.* 角色卡 -> .chara zip")
    p_exp.add_argument("card_id", help="角色卡 id(如 card.ying), 在 mods/ 下找")
    p_exp.add_argument("--out", required=True, help="输出 zip 路径")

    p_imp = sub.add_parser("import-chara", help=".chara zip -> mods/ 安装")
    p_imp.add_argument("zip_path", help=".chara zip 路径")
    p_imp.add_argument("--activate", action="store_true", help="装完设为当前角色(config)")

    args = parser.parse_args(argv)

    if args.cmd == "export-chara":
        card_dir = os.path.join(paths.MODS_DIR, args.card_id)
        if not os.path.isdir(card_dir):
            print("[ERROR] 角色卡不存在: %s" % card_dir)
            return 2
        try:
            new_id, n = export_chara(card_dir, args.out)
            print("导出完成: %s (%d 个文件) -> %s" % (new_id, n, args.out))
            return 0
        except ValueError as e:
            print("[ERROR] %s" % e)
            return 2
    if args.cmd == "import-chara":
        try:
            new_id, dest = import_chara(args.zip_path, activate=args.activate)
            print("安装完成: %s -> %s%s" % (new_id, dest,
                  "(已设为当前角色)" if args.activate else ""))
            return 0
        except ValueError as e:
            print("[ERROR] %s" % e)
            return 2

    # 默认: 数据迁移
    if not os.path.isdir(args.source):
        print("[ERROR] 源目录不存在: %s" % args.source)
        return 2
    report = migrate(args.source, paths.DATA_DIR, dry_run=args.dry_run)
    print("迁移%s:" % ("计划(dry-run)" if args.dry_run else "完成"))
    for kind, target in report["writes"]:
        print("  %-12s -> %s" % (kind, target))
    for b in report["backups"]:
        print("  备份: %s" % b)
    for s in report["skipped"]:
        print("  [跳过] %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
