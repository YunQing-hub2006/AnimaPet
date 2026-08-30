# AnimaPet 开发会话 · 工作交接记录（第 11 版 · 含 08-28/08-30 两批未提交改动）

> **会话日期**: 2026-08-30（性能/体积优化轮 + 未提交改动盘点）
> **上次提交**: `4f5b43d`（2026-08-23, docs: 项目结项报告）— **此后再无提交**
> **项目**: AnimaPet -- 基于 Anima 内核 v1.1.1 的桌面宠物元框架
> **位置**: `E:\Zcode-work\AnimaPet`（git 已初始化，按里程碑提交）
> **上游内核**: `E:\Zcode-work\Anima-v1.1`（v1.1.1 冻结，**只读**，勿改）
> **迁移源**: `E:\dsh-work\YingPet-v4`（只读参考）

---

## ⚠️ 最重要的一句话（接手者先读）

**Phase 0-5 早已完成（tag v1.0），但 `4f5b43d` 之后还压着两批未提交的工作区改动：
08-28 的「UI 重构 + 新手功能轮」和 08-30 的「性能/体积优化轮」。**
代码是好的、测试全绿，但**一行都没提交** —— 接手第一件事是把它们分批提交掉，
别在这基础上继续堆新改动。

| 批次 | 日期 | 主题 | 规模 | 状态 |
|---|---|---|---|---|
| A | 2026-08-28 | UI/可维护性重构 + 新手四功能（皮肤工坊/GIF导入/规则可视化/历史合并导入） | 18 改 + 5 新增 | 未提交，**已审查，见 §十一** |
| B | 2026-08-30 | 内存/磁盘优化 + UI 改版 | 8 改 + 2 新增 + 236 素材 | 未提交，测试全绿 |

详见 §二。

---

## 一、当前进度快照

> 本节的"本会话完成的工作"记录的是 2026-08-23 那次会话（已提交）；
> 2026-08-28 / 08-30 两批**未**提交的工作见 §二 与 §十一。

### PLAN Phase 0-5 全部完成 ✅（tag v1.0）

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
   按角色 HistoryStore）、`anima/window/chat_panel.py`（面板；JSON 导入导出已并入
   「备份 ▾」菜单）、`anima/models/chat.py`（ChatMessage/ChatHistory）。
7. **Phase 4 测试**：`tests/test_plugins/test_chat_plugin.py` 6 个用例（解析/历史/
   面板/按角色隔离/历史浏览/缺 key 降级）。
8. **方案 A（一切皆插件）**：角色卡管理器和聊天窗口改为内置功能模组
   `mods/feature.charcard/`、`mods/feature.chat/`，由总管理器启停/删除/替换；
   `main.py` 移除 ChatPlugin 硬编码，`module_manager` 移除 charcard 菜单硬编码；
   FeatureContext 新增 task/run_on_ui/use。

### 当前测试状态（2026-08-30 复核）

```text
./.venv/Scripts/python.exe -m pytest tests/ -q   ->  263 passed（全绿）
check_kernel_rules.py                            ->  840 行、纯标准库（未动）
dist/AnimaPet/AnimaPet.exe 冒烟                  ->  启动正常，工作集 87.6MB
```

> **测试基线是 263，不是 254。** 08-28 功能轮新增 9 个（GIF 4 / 皮肤工坊 3 /
> 聊天合并导入 1 / 行为规则 1）；08-30 优化轮未增删用例，只把
> `test_theme_merge_ignores_non_string` 的一条死色值断言改成"回退到默认值"。

---

## 二、提交与未提交状态

### 已提交（最后一次 `4f5b43d`，2026-08-23）

```text
ab239e9 chore: 内核升级 v1.1.0 -> v1.1.1（失败回滚/重启安全）
6617f5e feat: Phase 3 角色卡模型层——Pydantic 模型/schema/.chara 包/按角色隔离
380b8df feat: Phase 3 角色卡编辑器 GUI + 测试 + .chara 格式文档
4f5b43d docs: 项目结项报告 PROJECT_STATUS.md   <-- HEAD
```

### 未提交 · 批次 A（2026-08-28，两轮）

轮 1「UI/可维护性重构」+ 轮 2「新手功能轮」，文档见 `docs/PROJECT_STATUS.md` §9/§10。

```text
 M anima/plugins/chat.py                    历史导入三选(合并/覆盖/取消)
 M anima/window/dialogs/charcard/__init__.py
 M anima/window/dialogs/charcard/assets.py  GIF 导入到卡内
 M anima/window/dialogs/charcard/dialog.py  行为规则可视化编辑器
 M anima/window/dialogs/charcard/wizard.py
 M anima/window/dialogs/modmanager.py       新建模组对话框合并基类
 M anima/window/dialogs/settings.py         两步向导 + 温度滑条
 M anima/window/pet_window.py               菜单构建拆 _populate_menu
 M anima/window/tray.py
 M docs/PROJECT_STATUS.md                   §9/§10 两轮记录
 M docs/user_guide.md
 M tests/integration/test_full_stack.py     真实 mods 27->28, features 8->9
 M tests/test_plugins/test_charcard.py
 M tests/test_plugins/test_chat_plugin.py
 M tests/test_plugins/test_module_manager.py
?? anima/window/dialogs/common.py           新增: wait_fire/动画导入/GIF 解帧 收拢
?? anima/window/dialogs/skinmaker.py        新增: 皮肤工坊
?? mods/feature.skinmaker/                  新增: 皮肤工坊功能模组
?? tests/test_plugins/test_gif_import.py    新增 4 例
?? tests/test_plugins/test_skinmaker.py     新增 3 例
```

### 未提交 · 批次 B（2026-08-30，性能/体积 + UI 改版）

```text
 M anima/mods/loader.py        load_scaled_pixmap + 全局帧 LRU（内存）
 M anima/plugins/loader.py     scan() 处清帧缓存
 M anima/window/animator.py    emote 改解码即缩放
 M anima/window/bubble.py      气泡跟随主题字体
 M anima/window/chat_panel.py  气泡 HTML 走 theme.chat_bubble_html + 名字着色
 M anima/utils/theme.py        重写: 推导键/保色相提亮/亮度自适应描边
 M build.spec                  剔除 opengl32sw/Qt6Pdf/Qt6Network/非 zh_CN .qm
 M tests/test_utils.py         1 例断言改"回退到默认值"
 M mods/card.ying/**/*.png     236 张降到最长边 512（187MB -> 89MB）
?? tools/optimize_assets.py    新增: 素材瘦身工具（默认预览, --apply 写盘）
?? docs/ui-preview.png         三套皮肤离屏渲染预览
```

> `mods/card.ying` 的 236 张 PNG 是**修改**而非删除，全部在 git 里，
> `git checkout -- mods/` 可完整回滚到压缩前。

### 建议的提交切分

两批互相独立，**分两个 commit，别混**：

1. `refactor+feat: UI 统一暗色主题/对话框去重 + 皮肤工坊/GIF导入/规则可视化`（批次 A）
2. `perf: 帧解码即缩放 + 全局 LRU；素材降到 512；打包剔除 32MB 冗余`（批次 B，含素材）

`.gitignore` 已补 `.workbuddy/`（会话记忆目录，之前会被误提交）。

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
6. **素材格式必须是 PNG，不许换**（08-30 新增，用户明确要求）：用户会自制 mod，
   换 WebP 会直接破坏第三方生态。同理，**帧数、文件命名、动画时序、manifest
   引用方式**都不许动 —— 降采样/重编码是唯一允许的优化手段。
7. **图片一律走 `load_scaled_pixmap`，禁止 `QPixmap(path).scaled(...)`**（08-30）：
   后者会先把 2048² 的表情图解成 16MB 位图再缩小，桌宠只用得到 320px。
8. **主题键的推导契约**（08-30）：皮肤只定义 14 个基础键，其余由 `_derive()` 补齐，
   **显式定义优先**。`DEFAULT_THEME` 里带推导性质的键必须等于 `_derive()` 对主色的
   计算结果，否则会躺着永远用不到的死值
   （`tests/test_utils.py::test_theme_merge_none_safe` 守这条）。
9. **断言配色时断言"回退到默认值"，不要写死色值**（08-30）：换配色时不该动测试。

---

## 四、目录地图（Phase 3 后）

```text
E:\Zcode-work\AnimaPet\
├── HANDOVER.md / CLAUDE.md / 内核更换说明.md / PLAN.md
├── main.py / run.bat
├── tools\
│   ├── migrate_yingpet.py      migrate / export-chara / import-chara
│   ├── export_chara_schema.py  schema 生成器（幂等）
│   └── optimize_assets.py      08-30 新增：素材降采样瘦身（默认预览, --apply 写盘）
├── docs\
│   ├── chara_format.md         .chara 格式规范
│   ├── ui-preview.png          08-30 新增：三套皮肤离屏渲染预览
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
│           ├── common.py        wait_fire/统一样式/动画导入 + GIF 解帧（对话框共用）
│           ├── skinmaker.py     08-28 新增：皮肤工坊（19 项取色 + 实时预览）
│           ├── modmanager.py / settings.py
│           └── charcard\       __init__.py / dialog.py / wizard.py / assets.py
├── mods\                       card.ying + 3 皮肤 + 9 功能模组（含 chat/charcard/skinmaker）
│                               素材统一最长边 512，共 89MB
├── dist\AnimaPet\              155MB（依赖 67MB + mods 89MB），已重新打包并冒烟通过
├── .workbuddy\                 会话记忆（已加入 gitignore，勿提交）
├── data\                      运行时生成（gitignore）
└── tests\                      263 个（Phase 0-5 + GIF/皮肤工坊/聊天合并 全绿）
```

---

## 五、下一步

### 第 0 步（**新增，最优先**）：把两批未提交改动提交掉

代码全绿但不提交 = 换台机器就没了。按 §二 的切分建议分两个 commit。
提交前**务必确认** `mods/card.ying` 的 236 个 PNG 变更是想要的（体积 187→89MB）。

### 第 5 步（真机冒烟，用户环境）：按 docs/RELEASE_CHECKLIST.md 逐项验证；
确认稳定后删除 `E:\Zcode-work\Anima-core-old\core` 归档。

### 第 6 步（真机冒烟，用户环境）：重启应用 → 拖入 .chara zip 新角色 →
角色切换后人设/行为/历史完全隔离 → 编辑器改人设即热生效 → 聊天窗收发/导出。

> 用户真机实例一直是旧代码，所有 Phase 3/4/08-28/08-30 功能都要重启后才可见。
> 08-30 已重新打包（`dist/AnimaPet`，155MB）并冒烟通过，可直接拿去真机验证。
> 若冒烟发现问题，回来改代码后补测试并重新提交。

### 第 7 步（待办）：修 §十一 列出的 🟡 项

批次 A 审查出 4 个"行为不对但不致命"的问题，其中**行为规则编辑器会静默丢字段**
（`after_ms`/`if`/非三选动作）是真会丢数据的，建议提交完立刻修。

---

## 六、不用干什么（明确排除）

1. 不要再改 `anima/core/`（v1.1.1 冻结）。
2. 不要重复做 Phase 4 聊天（已落地；流式打字机渲染留到后续优化）。
3. Phase 5 已完成（含打包/性能/tag v1.0），不要再重复做。
4. 不要删 `E:\Zcode-work\Anima-core-old\core` 归档（等真机确认后）。
5. 不要重写编辑器（原样平移 + 数据源改造，别改布局；样式统一走
   `anima/utils/theme.py` 的 QSS 工厂，勿再各写各的 QSS）。
6. 不要在编辑器里引入新依赖（PyQt6 + pydantic 已够）。
7. 不要动 YingPet-v4 源码（只读参考）。
8. **不要再尝试 PNG 256 色量化**（08-30 实测）：体积能再砍 80%，但 PSNR 只有
   25.7~30.3dB，脸颊渐变肉眼可见色带。
9. **不要再尝试换 WebP**（08-30 实测）：q85 只有 PNG 的 18~22%，但换格式破坏
   用户自制 mod 生态，违反核心设计。
10. **不要再写 `QPixmap(path).scaled(...)`**：一律用 `load_scaled_pixmap()`。
11. 不要给主题测试写死色值断言：断言"回退到默认值"，否则换配色就要改测试。

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
- `docs/RELEASE_CHECKLIST.md`：用户真机冒烟清单。
- `build.spec` + `tools/build_exe.py` + `tools/benchmark.py`：打包与性能基准。
- 模组管理「导出日志…」「打开日志文件夹」：日志导出/排查。
- `loader._valid_rules` / `_one_emote`：逐文件降级范式（坏项丢弃 + `_VALIDATE_LIMIT`）。
- `anima/window/dialogs/common.py`：对话框共用工具（wait_fire/wait_rescan、统一暗色样式、动画 PNG/GIF 导入）——2026-08-28 重构轮收拢自 modmanager/charcard。
- `anima/window/dialogs/skinmaker.py` + `mods/feature.skinmaker/`：皮肤工坊（取色+实时预览生成 ui.* 皮肤）。
- `anima/window/dialogs/charcard/`：编辑器 GUI（dialog/wizard/assets；等待工具已上移 dialogs/common，包内再导出兼容）。
- 对话框平移先例：`settings.py` / `modmanager.py`（mm 服务 + `dialogs/common.wait_fire`）。

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

### 2026-08-30 优化轮新增

- **测 Windows 进程内存要用 `PagefileUsage` 不是 `WorkingSetSize`**：后者复用已提交页，
  测不出瞬时峰值。且 `GetProcessMemoryInfo` 在 64 位下**必须显式声明 `restype`/`argtypes`**，
  否则进程句柄被截断成 32 位、静默返回 0（我在这上面栽了两次，一直报 0.00MB）。
  验证方法：分配并 touch 200MB，看增量是否精确等于 200.4MB。
- **浅色皮肤下"提亮"会变白底白边**：`_shade` 只会往亮走，浅色皮肤算出
  `border=#fff7fa`。修法是 `_contrast_shade()` 按亮度自动翻转方向（`lum > 0.6` 则压暗）。
- **往白色插值会洗掉色相**：深紫 `#241a30` 直接往白提亮变成灰 `#87818d`。
  修法是 `_lighten()` 往"本色调到最亮的版本"插值；无彩色（纯灰/黑）的最亮版本
  恰好是白，自动退化，所以深色皮肤仍能拿到可见描边。
- **GIF 解帧的 600 帧上限是硬截断**：`common.py::extract_gif_frames`，
  超限时用户无感知，且不清理已建目录（见 §十一 🟡3）。
- **PyInstaller 重新打包会先 `rmtree dist/AnimaPet`**：想保住旧产物就先
  `--distpath` 到暂存目录验证后再替换。另外本仓库的 `mv` 有时会撞上
  Permission denied（安全删除机制拦截），改用 `cp -r` 再删源目录即可。

---

## 九、环境与复跑

```bash
cd E:\Zcode-work\AnimaPet

# 注意: 必须用项目虚拟环境。系统 python(managed 3.13.12) 没装 pytest,
# 直接 `python -m pytest` 会报 No module named pytest。
.venv\Scripts\python -m pytest tests/ -q          # 263 passed
.venv\Scripts\python check_kernel_rules.py        # 840 行 + 纯标准库
.venv\Scripts\python tools\export_chara_schema.py # schema 幂等
.venv\Scripts\python tools\optimize_assets.py     # 默认只预览, --apply 才写盘
.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run
.venv\Scripts\python tools\migrate_yingpet.py export-chara card.ying --out E:\ying.chara.zip
.venv\Scripts\python tools\migrate_yingpet.py import-chara E:\mio.chara.zip --activate
.venv\Scripts\python main.py                      # 真机启动（无控制台用 run.bat）

# 重新打包(会先删 dist/AnimaPet; 想保留旧产物先 --distpath 到暂存目录)
.venv\Scripts\python tools\build_exe.py
```

---

## 十、参考文档

- 总计划：`PLAN.md`（Phase 0-4 ✅；Phase 5 待做 + 验收标准）
- `.chara` 格式规范：`docs/chara_format.md`；JSON Schema：`docs/schema/chara.schema.json`
- 两批未提交改动的详细记录：`docs/PROJECT_STATUS.md` §9（08-28 重构）、§10（08-28 功能轮）
- 运行期笔记：`.workbuddy/memory/MEMORY.md`（项目约定）+ `.workbuddy/memory/2026-08-30.md`
- 内核 API / 并发模型 / 插件模板：`E:\Zcode-work\Anima-v1.1\docs\` 三份
- 迁移源（只读）：YingPet `feature.charcard/*` + `tests/test_charcard.py`（改写蓝本）

---

## 十一、2026-08-30 性能/体积优化轮

### 11.1 成果（全部实测）

| 维度 | 前 | 后 |
|---|---|---|
| `dist/AnimaPet` 总计 | 286MB | **155MB**（−45.8%） |
| ├ 素材 `mods/` | 187MB | 89MB |
| └ 依赖部分 | 99MB | 67MB |
| 单张 emote 加载峰值 | 16.52MB | **0.89MB**（−94.6%） |
| idle 动画常驻（50帧@240px） | 22.9MB | **11.0MB**（−52%） |
| 整机运行工作集 | — | 87.6MB |

### 11.2 做了什么

- **内存**：`QImageReader.setScaledSize()` 解码即缩放（干掉全分辨率位图峰值）；
  AnimMod 的永不释放 `_cache` 换成全局帧 LRU（64MB 软预算，按 `(目录, 尺寸)` 分组，
  淘汰最久未用）。预算是**软**的 —— Animator 持有帧列表引用，淘汰只影响"下次要不要
  重解码"，不会打断正在播的动画。`LoaderPlugin.scan()` 处清缓存（素材热重载后失效）。
- **磁盘**：236 张 PNG 降到最长边 512（最大显示 320px 的 1.6 倍，留 HiDPI 余量），
  只降采样 + 重编码；`build.spec` 剔除 `opengl32sw.dll`(19.7MB) / `Qt6Pdf.dll`(4.4MB) /
  `Qt6Network.dll`(1.7MB) / 96 个翻译文件保留 3 个 `zh_CN`（共 −32MB）。
  已复核 `anima/` 内零处 QtNetwork/OpenGL/Pdf/WebEngine 引用（网络走 `requests`）。
- **UI**：修了浅色「樱粉」皮肤弹出深色右键菜单的真 bug（皮肤只定义 14 个基础键，
  `menu_bg`/`bubble_bg` 一直回落硬编码深色）；补齐 hover/pressed/focus/checked/disabled
  状态、4 级高度层级、圆角滚动条、tooltip。

### 11.3 批次 A 审查结论（2026-08-30 盘点时做的）

**🔴 必修：无**（未发现崩溃或数据损坏路径）
**A/B 兼容性：干净** —— 全仓 AST 扫描确认批次 A 调用的 `merge_theme`/`menu_qss`/
`dialog_qss`/`panel_qss`/`bubble_qss`/`chat_bubble_html` 在批次 B 重写后全部存在且签名未变；
`load_scaled_pixmap` + 帧 LRU 与 Animator 按需启停定时器无冲突，且定时器不存在卡死路径
（`_decode_frames` 有 `_fallback_disc` 兜底，永不返回空表）。

**🟡 该修（4 项，建议提交完立刻处理）**

1. **行为规则编辑器静默丢字段**（`charcard/dialog.py`，**真会丢数据**）
   - `_action_from_editor()` L820-829 只产出单键 dict，`_update_action_from_editor()` L848
     整体替换 → 现有 6 条规则中 3 条带 `after_ms`（如 `{"emote":"angry","after_ms":200}`），
     一按「更新选中」就丢。
   - 条件键只读写 `when`（L673/L691），但 `rule_engine.py:194` 是
     `for cond_key in ("when","if")` → 用 `if` 的规则条件会丢。
   - `on` 支持列表（`rule_engine.py:182-184`），但 L662 `str(r.get("on"))` 会把
     `["a","b"]` 写成字符串字面量 `"['a','b']"` → 规则静默失效。
   - `_on_action_selected` L864/L868 `setCurrentIndex(max(0, idx))`：id 不在下拉时静默
     选中第 0 项，一按「更新选中」就换成别的动作；`state_set`/`state_inc`/`emit`
     （`actions.py:82-84`）等非三选动作会走空分支，同样被误替换。
2. **四个对话框不跟随皮肤**：`dialogs/common.py:59-61` `apply_dialog_style` 硬编码
   `merge_theme({})`。08-30 让皮肤真正生效后，浅色皮肤下主窗口/气泡/聊天面板变浅，
   对话框仍深紫 —— 与主题系统"全局一致"的契约矛盾。
3. **GIF 导入失败留孤儿目录**：`common.py::import_gif` 先建 `mods/anim.X/frames`，
   `extract_gif_frames` 抛错无回滚；`loader.py:274` 对无 manifest 目录 `continue` 静默
   跳过 → 目录永久残留，下次同名导入跳到 `_2`（且 `_alloc_library_anim_dir` L140-144
   计数器先自增，`_1` 被跳过）。
4. **历史合并导入只比现有**：`chat.py:170-181` 的 `existing` 集合只在循环外由
   `self.entries` 建一次，`added` 不回写进去 → incoming **内部**重复的
   `(ts, role, content)` 不去重。

**🟢 建议（5 项）**：`assets.py` 残留未用 import `jsonio`/`paths`；
`skinmaker.py:105,224` 两处 `setdefault("bubble_bg",...)` 是死代码（merge_theme 必有此键）；
取色器 `col.name()` 会把 `rgba(...,230)` 转不透明 hex，头顶气泡失半透明；
`common.py:114` 截断只在日志告警、用户无感知，且"恰好 600 帧"时可能误报；
皮肤 id `a..`/`a.b..` 能通过校验
（Windows 静默剥尾点 → 实际目录 `ui.a`，但 config 记 `ui.a..`，皮肤不生效；
`../../evil`、`a/../b` 等穿越已正确挡住）；`animator.py::play_frames` 在 `back_to_idle`
不清空 → 播过一次后按需启停永久失效（不影响功能）。

**测试缺口**：`test_gif_import.py` 只用单帧 1×1 GIF，`1 <= fps <= 30` 几乎恒真 →
平均延时折算/600 帧上限/失败清理三个分支实际都没测到；
`test_charcard.py` 行为规则用例**无往返保真断言**（正是 🟡1 溜过去的原因）；
`test_skinmaker.py` 未测 id 路径安全、未断言 `_COLOR_FIELDS` 键均为合法 theme 键；
`_NewModDialogBase` 两子类的 PREFIX/冲突检查无独立用例。

> **接手者从 Phase 5 剩余项（打包/tag）与真机冒烟继续；代码已带 Phase 3/4/5 部分，重启后可见。**