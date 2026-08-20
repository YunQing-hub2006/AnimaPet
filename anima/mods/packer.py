# -*- coding: utf-8 -*-
"""模组打包/导入导出(无 UI 纯函数核心, 源自 YingPet feature.packer)。"""
import json
import os
import re
import shutil
import zipfile

from anima.utils import log

_log = log.get("packer")
TYPE_NAMES = {"character": "角色", "anim": "动画", "emote": "表情", "idle": "台词",
              "behavior": "行为", "feature": "功能", "ui": "皮肤"}

def safe_zip_members(zf):
    """校验压缩包全部成员路径: 拒绝绝对路径/..穿越/盘符。返回 (根目录名 or '', 相对路径列表)。"""
    names = zf.namelist()
    if not names:
        raise ValueError("压缩包是空的")
    rels = []
    for n in names:
        n2 = n.replace("\\", "/")
        if n2.startswith("/") or ":" in n2.split("/")[0] or ".." in n2.split("/"):
            raise ValueError("压缩包里有可疑路径: %s" % n)
        rels.append(n2)
    tops = {r.split("/", 1)[0] for r in rels if r and not r.endswith("/")}
    # 允许两种布局: 全部在唯一顶层目录下 / 直接平铺(manifest.json 在根部)
    if len(tops) == 1:
        top = next(iter(tops))
        if not any(r == top + "/manifest.json" or r.startswith(top + "/") and r != top for r in rels):
            top = ""
    else:
        top = ""
    return top, rels


def read_manifest_from_zip(zf, top):
    """从 zip 里读 manifest.json → dict。找不到抛 ValueError。"""
    target = (top + "/manifest.json") if top else "manifest.json"
    if target not in zf.namelist():
        raise ValueError("压缩包里没有 manifest.json(不是模组包?)")
    try:
        return json.loads(zf.read(target).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError("manifest.json 不是合法 JSON: %s" % e)


def unique_target_dir(mods_dir, mod_id):
    """mods/ 下的目标目录, 冲突时自动改名: id、id_2、id_3…"""
    candidate = os.path.join(mods_dir, mod_id)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(mods_dir, "%s_%d" % (mod_id, n))
        n += 1
        if n > 999:
            raise ValueError("重名模组太多: %s" % mod_id)
    return candidate


def export_mod(mod_dir, dest_zip):
    """把模组文件夹打包为 zip(顶层目录 = 模组文件夹名)。返回条目数。"""
    mod_dir = os.path.abspath(mod_dir)
    root_name = os.path.basename(mod_dir)
    count = 0
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _dirs, files in os.walk(mod_dir):
            for f in files:
                full = os.path.join(base, f)
                rel = os.path.relpath(full, mod_dir)
                # 跳过编辑器/系统垃圾文件
                if rel.split(os.sep)[0] in ("__pycache__", ".git") or f.endswith((".pyc", ".tmp")):
                    continue
                zf.write(full, root_name + "/" + rel.replace(os.sep, "/"))
                count += 1
    return count


def import_mod_zip(zip_path, mods_dir):
    """导入一个模组 zip 到 mods/。返回 (新id, 新目录)。任何问题抛 ValueError。"""
    with zipfile.ZipFile(zip_path) as zf:
        top, rels = safe_zip_members(zf)
        manifest = read_manifest_from_zip(zf, top)
        mod_id = str(manifest.get("id", "")).strip()
        if not mod_id or not re.fullmatch(r"[A-Za-z0-9._\-]+", mod_id):
            raise ValueError("manifest 里的 id 非法: %r" % manifest.get("id"))
        mtype = str(manifest.get("type", "")).strip().lower()
        if mtype not in TYPE_NAMES:
            raise ValueError("未知模组类型: %r" % manifest.get("type"))
        # 装到 mods/<id>, 目录冲突自动改名; 若改名了还要回写 manifest 里的 id
        dest = unique_target_dir(mods_dir, mod_id)
        new_id = os.path.basename(dest)
        try:
            os.makedirs(dest)
            for n in zf.namelist():
                n2 = n.replace("\\", "/")
                if not n2 or n2.endswith("/"):
                    continue
                rel = n2[len(top) + 1:] if top else n2
                if not rel or rel.startswith("__pycache__/") or rel.endswith(".pyc"):
                    continue
                target = os.path.join(dest, *rel.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(n) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
            if new_id != mod_id:   # 冲突改名 → 回写 manifest, 保证 id 与目录一致
                manifest["id"] = new_id
                _save_manifest(dest, manifest)
        except ValueError:
            shutil.rmtree(dest, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise ValueError("解压失败: %s" % e)
    return new_id, dest


def _save_manifest(dest, manifest):
    """写 manifest.json(打包导入后回写 id 用, 只经本模块内部调用)。"""
    path = os.path.join(dest, "manifest.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
