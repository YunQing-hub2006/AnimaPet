# AnimaPet 开发会话 · 工作交接记录（第 9 版 · Phase 3+4 完成 + Phase 5 部分）

> **会话日期**: 2026-08-23（Phase 4 完成：聊天/适配器/历史/测试落地）
> **项目**: AnimaPet -- 基于 Anima 内核 v1.1.1 的桌面宠物元框架
> **位置**: `E:\Zcode-work\AnimaPet`（git 已初始化，按里程碑提交）
> **上游内核**: `E:\Zcode-work\Anima-v1.1`（v1.1.1 冻结，**只读**，勿改）
> **迁移源**: `E:\dsh-work\YingPet-v4`（只读参考）

---

## ⚠️ 最重要的一句话（接手者先读）

**Phase 3/4 已全部完成；Phase 5 部分完成（tray/开发指南/README），剩余打包/tag + 真机冒烟。**
当前收尾后为干净状态；提交历史：① 内核升级 v1.1.1；② Phase 3 数据层；
③ Phase 3 编辑器/测试/文档；④ Phase 4 聊天（本版收尾提交）。

---

## 一、当前进度快照（截至 2026-08-23）

### PLAN Phase 0-4 全部完成 ✅；Phase 5 部分完成（打包/tag 待确认）

Phase 3 五项子任务状态：

| # | PLAN 子任务 | 状态 |
|---|---|---|
| 1 | Pydantic 模型 + JSON Schema 导出 | ✅ 完成（`anima/models/` + `docs/schema/chara.schema.json`，漂移测试） |
| 2 | 格式规范文档 + 迁移工具 card.* ↔ .chara 互转 | ✅ 完成（`docs/chara_format.md` + `export-chara`/`import-chara`） |
| 3 | charcard 编辑器 6 页签 GUI + Pydantic 校验 | ✅ 完成（`anima/window/dialogs/charcard/`，菜单接入 module_manager） |
| 4 | 多角色并存与切换上下文隔离 | ✅ 完成（`character_manager.history_dir` + 迁移按角色分流） |
| 5 | ZIP 形式 .chara 加载（packer 防护复用） | ✅ 完成（packer 扩展 + id/类型归一） |

Phase 4 四项子任务已全部完成：`anima/adapters/`（LLMProvider/openai_compat）、
`anima/plugins/chat.py` + `window/chat_panel.py`、按角色历史存储（搜索/单条删除/
JSON 导入导出）、`stream` 配置预留。

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
5. **PLAN.md 回填**：Phase 3/4 勾选 + 验收说明；HANDOVER 第 8 版。
6. **Phase 4 聊天**：`anima/adapters/{base,openai_compat}.py`（async LLMProvider、
   sync requests 包 to_thread、解析/降级）、`anima/plugins/chat.py`（ChatFeature 控制器 +
   按角色 HistoryStore）、`anima/window/chat_panel.py`（面板 + JSON 导入导出按钮）、
   `anima/models/chat.py`（ChatMessage/ChatHistory）。
7. **Phase 4 测试**：`tests/test_plugins/test_chat_plugin.py` 6 个用例（解析/历史/
   面板/按角色隔离/历史浏览/缺 key 降级）。
8. **方案 A（一切皆插件）**：角色卡管理器和聊天窗口改为内置功能模组
   `mods/feature.charcard/`、`mods/feature.chat/`，由总管理器启停/删除/替换；
   `main.py` 移除 ChatPlugin 硬编码，`module_manager` 移除 charcard 菜单硬编码；
   FeatureContext 新增 task/run_on_ui/use。

### 当前测试状态

```text
pytest tests/ -> 252 passed（约 21s，全绿）
check_kernel_rules.py -> 840 行、纯标准库（v1.1.1 内核，未动）
```

---

## 二、提交与未提交状态

已完成提交：

```text
ab239e9 chore: 内核升级 v1.1.0 -> v1.1.1（失败回滚/重启安全）
6617f5e feat: Phase 3 角色卡模型层——Pydantic 模型/schema/.chara 包/按角色隔离
380b8df feat: Phase 3 角色卡编辑器 GUI + 测试 + .chara 格式文档
（Phase 4 聊天 commit 随本次收尾提交）
```

仍建议：`.mimosa/` 已加入 .gitignore。

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
│   ├── models\                 Pydantic 校验层（角色卡 + 聊天）
│   ├── adapters\               Phase 4 LLM 适配器（base/openai_compat）
│   ├── plugins\...             config/state/actions/loader/rule_engine/…/character_manager/module_manager/chat
│   ├── mods\...                loader/packer/registry
│   ├── utils\...                paths/log/jsonio/theme
│   └── window\
│       ├── pet_window.py / animator.py / bubble.py / chat_panel.py
│       └── dialogs\
│           ├── modmanager.py / settings.py
│           └── charcard\       __init__.py / dialog.py / wizard.py / assets.py
├── mods\                       card.ying + 3 皮肤 + 6 功能模组
├── data\                      运行时生成（gitignore）
└── tests\                      250 个（Phase 3+4 全绿）
```

---

## 五、下一步（Phase 5 + 真机冒烟）

### 第 5 步（Phase 5 生态与收尾）：已完成 tray、docs/plugin_dev_guide.md、
README、tools/new_plugin.py；剩余 PyInstaller 打包、性能基准、tag v1.0（待用户确认）。

### 第 6 步（真机冒烟，用户环境）：重启应用 → 拖入 .chara zip 新角色 →
角色切换后人设/行为/历史完全隔离 → 编辑器改人设即热生效 → 聊天窗收发/导出。

> 用户真机实例一直是旧代码，所有 Phase 3/4 功能都要重启后才可见。
> 若冒烟发现问题，回来改代码后补测试并重新提交。

---

## 六、不用干什么（明确排除）

1. 不要再改 `anima/core/`（v1.1.1 冻结）。
2. 不要重复做 Phase 4 聊天（已落地；流式打字机渲染留到后续优化）。
3. Phase 5 是下一步，但打包/tag 需用户确认后执行。
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
- `character_manager.history_dir`：`data/characters/<id>/chat_history.json`（Phase 4 已接管）。
- `anima/adapters/`：LLMProvider/OpenAICompatProvider，任何异步 LLM 接入点。
- `anima/plugins/chat.py`：ChatFeature + HistoryStore（搜索/单条删除/JSON 导入导出），由 `mods/feature.chat` 驱动。
- `mods/feature.charcard/` + `mods/feature.chat/`：内置功能模组，总管理器可启停/删除/替换。
- `anima/window/tray.py`：系统托盘（角色/皮肤/退出）。
- `docs/plugin_dev_guide.md` + `tools/new_plugin.py`：第三方开发指南与脚手架。
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
- **Qt 线程调 async 的坑**：chat 面板信号在 Qt 主线程，不能直接 `asyncio.ensure_future`
  （无运行循环）。统一走 `module_manager.fire(coro)`（跨线程投递内核循环；
  单线程测试回退 create_task）。

---

## 九、环境与复跑

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python -m pytest tests/ -q          # 250 passed
.venv\Scripts\python check_kernel_rules.py        # 840 行 + 纯标准库
.venv\Scripts\python tools\export_chara_schema.py # schema 幂等
.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run
.venv\Scripts\python tools\migrate_yingpet.py export-chara card.ying --out E:\ying.chara.zip
.venv\Scripts\python tools\migrate_yingpet.py import-chara E:\mio.chara.zip --activate
.venv\Scripts\python main.py                      # 真机启动（无控制台用 run.bat）
```

---

## 十、参考文档

- 总计划：`PLAN.md`（Phase 0-4 ✅；Phase 5 待做 + 验收标准）
- `.chara` 格式规范：`docs/chara_format.md`；JSON Schema：`docs/schema/chara.schema.json`
- 内核 API / 并发模型 / 插件模板：`E:\Zcode-work\Anima-v1.1\docs\` 三份
- 迁移源（只读）：YingPet `feature.charcard/*` + `tests/test_charcard.py`（改写蓝本）

> **接手者从 Phase 5 剩余项（打包/tag）与真机冒烟继续；代码已带 Phase 3/4/5 部分，重启后可见。**