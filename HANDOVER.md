# AnimaPet 开发会话 · 工作交接记录（第 7 版 · Phase 3 完成）

> **会话日期**: 2026-08-23（Phase 3 收尾：测试+提交+编辑器+文档全部落地）
> **项目**: AnimaPet -- 基于 Anima 内核 v1.1.1 的桌面宠物元框架
> **位置**: `E:\Zcode-work\AnimaPet`（git 已初始化，按里程碑提交）
> **上游内核**: `E:\Zcode-work\Anima-v1.1`（v1.1.1 冻结，**只读**，勿改）
> **迁移源**: `E:\dsh-work\YingPet-v4`（只读参考）

---

## ⚠️ 最重要的一句话（接手者先读）

**Phase 3 已全部完成并提交，剩余只有用户真机冒烟（HANDOVER §五 第 5 步）。**
当前工作区已无 Phase 3 的未提交改动（仅 `.mimosa/` 建议 gitignore）。
提交历史：① 内核升级 v1.1.1；② Phase 3 数据层（模型/schema/.chara/按角色隔离）；
③ 本次 GUI+测试+文档 commit（编辑完本文档后提交）。

---

## 一、当前进度快照（截至 2026-08-23）

### PLAN Phase 0/1/2/3 全部完成 ✅；Phase 4/5 待做

Phase 3 五项子任务状态：

| # | PLAN 子任务 | 状态 |
|---|---|---|
| 1 | Pydantic 模型 + JSON Schema 导出 | ✅ 完成（`anima/models/` + `docs/schema/chara.schema.json`，漂移测试） |
| 2 | 格式规范文档 + 迁移工具 card.* ↔ .chara 互转 | ✅ 完成（`docs/chara_format.md` + `export-chara`/`import-chara`） |
| 3 | charcard 编辑器 6 页签 GUI + Pydantic 校验 | ✅ 完成（`anima/window/dialogs/charcard/`，菜单接入 module_manager） |
| 4 | 多角色并存与切换上下文隔离 | ✅ 完成（`character_manager.history_dir` + 迁移按角色分流） |
| 5 | ZIP 形式 .chara 加载（packer 防护复用） | ✅ 完成（packer 扩展 + id/类型归一） |

### 本会话完成的工作（已提交/待提交）

1. **Phase 3 数据层测试**（`tests/test_plugins/test_models.py`、`test_mods_layer.py`、
   `test_character_manager.py`、`test_tools.py` 新增 22 个用例）：模型别名/边界、
   load_card/save_card 往返、schema 漂移、逐文件降级、packer 归一、迁移分流。
2. **编辑器 GUI 平移**（`anima/window/dialogs/charcard/{__init__,assets,wizard,dialog}.py`）：
   数据源从 `FeatureContext` 改为 `module_manager` 服务；保存动作统一过
   `anima.models.load_card` 整体预检（坏数据弹错不落盘）；重扫走
   `mm.rescan()` + `_wait_rescan` 模式；`module_manager.enable` 增加菜单
   「角色卡管理器…」。
3. **test_charcard.py 改写**（`tests/test_plugins/test_charcard.py`，3 个用例）：
   管理器打开/卡内动画展示、四页签写回路由、新建向导→热加载→删除干净。
4. **格式规范文档**：`docs/chara_format.md`（目录结构、四 JSON 字段表、
   `format="chara-1"`、id 命名、双名兼容、zip 规范、校验边界两套语义）。
5. **PLAN.md 回填**：Phase 3 五项勾选 + 验收说明；HANDOVER 第 7 版。

### 当前测试状态

```text
pytest tests/ -> 244 passed（约 19s，全绿）
check_kernel_rules.py -> 840 行、纯标准库（v1.1.1 内核，未动）
```

---

## 二、提交与未提交状态

已完成提交：

```text
ab239e9 chore: 内核升级 v1.1.0 -> v1.1.1（失败回滚/重启安全）
6617f5e feat: Phase 3 角色卡模型层——Pydantic 模型/schema/.chara 包/按角色隔离
（本次收尾的 GUI+test_charcard+docs 将作为第三个 commit）
```

仍建议：`.mimosa/`（Mimosa 安全工具运行产物）加入 .gitignore 或忽略。

---

## 三、重要澄清与设计决策（勿偏离）

1. **校验边界分工**：`anima.models.load_card/save_card` = 整体校验（编辑器/工具
   保存把关，坏数据报 `ValueError` 带文件名）；`loader._build_card` = 逐文件降级
   （坏表情/规则/台词段丢弃记日志，其余照常）。测试两套语义都有覆盖。
2. **.chara 包格式**：物理结构 = YingPet card.* 文件夹 + `manifest.format="chara-1"`；
   zip 打包经 `packer.export_mod`，导入走 `packer.import_mod_zip`（Zip-Slip 防护）；
   `type="chara"` 装完必须回写 `type="card"` + id 补 `card.` 前缀。
3. **Behavior.on 必填非空**；rule_engine 同时支持 `when` 和 `if`，模型 extra=ignore
   只校验不裁剪，规则原文透传。
4. **编辑器保存语义**：人设/动画/台词/行为/表情页签改 `raw` dict 原样回写到
   source_file，但保存前整体预检（load_card）；新建向导生成自包含卡。
5. **其余沿用第 6 版**：TD1 双线程、QObject 亲和性、feature 禁用=完整卸载、
   jsonio 路径安全、main.py 互斥量在 `main()` 里。

---

## 四、目录地图（Phase 3 后）

```text
E:\Zcode-work\AnimaPet\
├── HANDOVER.md / CLAUDE.md / 内核更换说明.md / PLAN.md
├── main.py / run.bat
├── tools\
│   ├── migrate_yingpet.py      migrate / export-chara / import-chara
│   └── export_chara_schema.py  schema 生成器（幂等）
├── docs\
│   ├── chara_format.md         本版新增：.chara 格式规范
│   └── schema\chara.schema.json
├── anima\
│   ├── core\                   v1.1.1 内核（冻结勿改）
│   ├── models\                 Pydantic 校验层
│   ├── plugins\...             config/state/actions/loader/rule_engine/…/character_manager/module_manager
│   ├── mods\...                loader/packer/registry
│   ├── utils\...                paths/log/jsonio/theme
│   └── window\
│       ├── pet_window.py / animator.py / bubble.py
│       └── dialogs\
│           ├── modmanager.py / settings.py
│           └── charcard\       __init__.py / dialog.py / wizard.py / assets.py
├── mods\                       card.ying + 3 皮肤 + 6 功能模组
├── data\                      运行时生成（gitignore）
└── tests\                      244 个（Phase 3 全绿）
```

---

## 五、下一步（只剩真机冒烟）

### 第 5 步（真机冒烟，用户环境）：重启应用 → 拖入 .chara zip 新角色 →
角色切换后人设/行为/历史完全隔离 → 编辑器改人设即热生效。

> 用户真机实例一直是旧代码，所有 Phase 3 功能都要重启后才可见。
> 若冒烟发现问题，回来改代码后补测试并重新提交。

---

## 六、不用干什么（明确排除）

1. 不要再改 `anima/core/`（v1.1.1 冻结）。
2. 不要做 Phase 4（聊天/LLM）——只留了 `history_dir` 落点。
3. 不要做 Phase 5（tray/打包/README/tag）。
4. 不要删 `E:\Zcode-work\Anima-core-old\core` 归档（等真机确认后）。
5. 不要重写编辑器（原样平移 + 数据源改造，别改布局/样式）。
6. 不要在编辑器里引入新依赖（PyQt6 + pydantic 已够）。
7. 不要动 YingPet-v4 源码（只读参考）。

---

## 七、可继承的工作资产

- `anima.models.load_card/save_card`：编辑器/工具/迁移整体校验；Phase 4 人设注入可复用 `CharacterCard.system_prompt`。
- `tools/export_chara_schema.py`：改模型后重新生成 schema（测试断言同步）。
- `packer.import_mod_zip` + `migrate.import_chara`：拖入 zip 安装新角色入口。
- `migrate.export_chara`：规范化导出（format 标记 + 整体校验）。
- `character_manager.history_dir`：`data/characters/<id>/chat_history.json` 已定死，Phase 4 直接接管。
- `loader._valid_rules` / `_one_emote`：逐文件降级范式（坏项丢弃 + `_VALIDATE_LIMIT`）。
- `anima/window/dialogs/charcard/`：编辑器 GUI（dialog/wizard/assets + 包内 wait_fire 工具）。
- 对话框平移先例：`settings.py` / `modmanager.py`（mm 服务 + `_wait_fire` 模式）。

---

## 八、坑与经验（本会话新增）

- **packer 归一分支的坑**：`import_mod_zip` 里 `mod_id` 先归一为 `card.xxx` 后，
  `new_id != mod_id` 在无目录冲突时恒为 False，导致 `chara→card` 类型、id 前缀
  都没有回写 manifest（扫描仍报未知类型）。修复：用 `raw_id` 比较，`mtype=="chara"`
  必须无条件回写。测试 `test_packer_import_chara_normalizes_type_and_id` 已覆盖。
- **migrate chat_history 分流的坑**：计划项 kind 是 `chat_history[<id>]`，但复制分支
  只判断 `kind == "chat_history"`，导致按角色文件被当字符串写坏。修复：
  `kind.startswith("chat_history")`。测试 `test_migrate_chat_history_split_by_character` 已覆盖。
- **命令行中文/`\n` 转义**：写测试脚本时字符串里的换行转义容易在 heredoc/模板字面量
  中被二次解释，务必用 `ast.parse` 或 repr 检查生成文件后再跑。
- **菜单断言**：module_manager 新增「角色卡管理器…」后，`test_module_manager` 的三处
  feature_menu 断言已同步更新。
- **Mimosa hook / Jsonio**：仓库内写文件走 `jsonio.save`（项目根白名单 + 原子写），
  测试临时目录记得 monkeypatch `jsonio._BASE`。

---

## 九、环境与复跑

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python -m pytest tests/ -q          # 244 passed
.venv\Scripts\python check_kernel_rules.py        # 840 行 + 纯标准库
.venv\Scripts\python tools\export_chara_schema.py # schema 幂等
.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run
.venv\Scripts\python tools\migrate_yingpet.py export-chara card.ying --out E:\ying.chara.zip
.venv\Scripts\python tools\migrate_yingpet.py import-chara E:\mio.chara.zip --activate
.venv\Scripts\python main.py                      # 真机启动（无控制台用 run.bat）
```

---

## 十、参考文档

- 总计划：`PLAN.md`（Phase 0-3 ✅；Phase 4/5 待做 + 验收标准）
- `.chara` 格式规范：`docs/chara_format.md`；JSON Schema：`docs/schema/chara.schema.json`
- 内核 API / 并发模型 / 插件模板：`E:\Zcode-work\Anima-v1.1\docs\` 三份
- 迁移源（只读）：YingPet `feature.charcard/*` + `tests/test_charcard.py`（改写蓝本）

> **接手者从真机冒烟继续（第 5 步）；在此之前不要动 Phase 3 代码。**