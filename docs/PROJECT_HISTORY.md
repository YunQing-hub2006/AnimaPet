# AnimaPet 项目历史与参考（三份文档合并归档）

> **本文档说明**：本文档把原先三份内容重叠、部分已经过期的项目状态文档合并为**一份**，作为 AnimaPet 唯一的「进展 / 决策 / 经验」总档案。合并来源与原始口径如下：
>
> - `PLAN.md` —— **2026-08-18**，立项时的《AnimaPet 迁移开发计划》（文中自称"本计划"）。
> - `HANDOVER.md` —— **第 12 版**，会话日期 **2026-08-30**，《AnimaPet 开发会话 · 工作交接记录》。注意其 §一"本会话完成的工作"记的其实是 **2026-08-23** 那次会话（文档自己声明了这点）。
> - `docs/PROJECT_STATUS.md` —— **2026-08-23** 的《AnimaPet 项目结项报告》，**2026-08-28** 追加了 §9（UI/可维护性重构轮）与 §10（面向新手的功能轮）两篇附录。
>
> 合并原则：
> 1. **保留**：三份文档中只在某一处出现的实质内容（技术决策、映射表、目录结构、决策澄清、踩坑经验、审查结论、环境与复跑方式等）逐条保留，不改语意。
> 2. **压缩**：三份文档重复叙述的"Phase 0-5 已完成 ✅"进度表、按会话叙述的"今天做了什么"、逐提交罗列的内容索引，合并为一份时间线与一张总表。
> 3. **标注**：源文档之间口径不一致的地方（最典型的是测试数量，见**附录 A**）**不擅自取一个值**，而是并列说明；有疑问、有歧义之处在文中直接写"原文未解释 / 口径不明"。
> 4. 三份原文档的内容已全部并入本文档，合并完成后**已从工作区删除**（`PLAN.md`、`HANDOVER.md`、`docs/PROJECT_STATUS.md`）。如需逐字对照，可用 `git show <合并前的提交>:PLAN.md` 从 git 历史取回。

> ⚠️ **时效性提示：项目已经走过这三份文档**
> 本文档记录的内容截至 **2026-08-30**。此后项目继续演进，阅读时请注意：
> - **2026-09-03**：新增角色卡 `mods/card.dsh/`（配套生成工具 `tools/build_dsh_card.py`）。截至本文档写作时，该目录与工具在 git 中仍是**未跟踪的工作区新增内容**。
> - **2026-09-21**：内嵌内核升级 **v1.1.1 → v1.3.0 → v1.3.1**（提交 `0922f9b`，当前 `anima/core/__init__.py` 的 `__version__` 为 `"1.3.1"`）。
> - **内核升级记录现已归档到 `docs/kernel_upgrade.md`**（含 v1.3.0 的必改项、回滚副本位置、`tests/test_core/` 同步情况）。内核版本、更换步骤与最新测试口径请以该文档为准；本文档 §4.2（TD2）与 §9.2 只保留"当初为什么升级、怎么升级"的历史决策与截止 08-30 的记录。

---

## 目录

1. 项目背景与目标
2. 立项时的三份资产盘点（2026-08-18 口径）
3. 目录结构（目标结构 + 实际目录地图）
4. 关键技术决策 TD1–TD6 与相关约定
5. 迁移映射表（原文标注为"核心干货"）
6. 风险与对策（2026-08-18 立项口径）
7. 里程碑与阶段完成情况（三份文档进度表合并）
8. 最终交付物与未完成/未验证（2026-08-23 结项口径）
9. 项目规模与提交时间线
10. 重要澄清与设计决策（勿偏离）
11. 踩过的坑与经验
12. 不用干什么（明确排除）
13. 可继承的工作资产
14. 环境与复跑
15. 2026-08-28 追加轮之一：UI/可维护性重构
16. 2026-08-28 追加轮之二：面向新手的功能轮
17. 2026-08-30 性能/体积优化轮
18. 为什么没有继续推进（结项当时）
19. 未来若要复用/重启
20. 一句话总结
21. 参考文档
22. 附录 A：测试数量口径说明（253 / 254 / 263 / 268 / 346）
23. 附录 B：本文档的取舍说明（压缩了什么、丢弃了什么）
24. 2026-09-22 归档整理、渲染优化与后续修复（托盘 / API 排查）

---

## 1. 项目背景与目标

（源：`docs/PROJECT_STATUS.md` §1，2026-08-23 口径）

将 YingPet-v4（约 **6,681 行 Python** 的桌面宠物）迁移到自研的 Anima 插件内核上，核心设计是：

1. **一切皆插件**：用户可见功能（角色卡编辑器、聊天、天气、待办……）都应是可删、可换、可热重载的模组；
2. **内核不动**：Anima 内核责任单一（事件总线 / 插件生命周期 / 服务注册），业务全部在插件层；
3. **数据格式继承**：沿用 YingPet `card.*` 角色卡结构，规范化为 `.chara`，与聊天历史按角色隔离。

> 项目定位（结项报告抬头）：基于 Anima 内核 **v1.1.1** 的 Windows 桌面宠物元框架，**个人项目**，已按当前阶段收尾存档。
> 结项结论原文：**"代码与测试已完成到 v1.0，但未经真机持续使用验证，项目按『暂缓/存档』处理。"**

立项时的项目抬头（`PLAN.md`，2026-08-18）：

> **项目**：AnimaPet —— 基于 Anima 内核的桌面宠物元框架
> **性质**：将 `<YingPet-v4 源目录>`（6,681 行 Python）迁移到 Anima 插件内核（已冻结 v1.0）
> **落地位置**：`AnimaPet`
> **依据**：《Anima 桌面宠物元框架开发规划书》（本目录 .txt）+ YingPet-v4 实测架构盘点

---

## 2. 立项时的三份资产盘点（2026-08-18 口径）

（源：`PLAN.md` §一"现状盘点（三份资产）"）

### 2.1 Anima 内核（`<内核上游目录>`，已完成 ✅）

规划书 Phase 0 的交付物已经存在：**735 行纯标准库内核，104 个测试全绿，总覆盖率 99%**（各模块 ≥97%），含：

- App / EventBus / ServiceRegistry / LifecycleManager / Context / EffectTracker / Plugin / 异常体系；
- Kahn 拓扑排序、LIFO 副作用回滚、通配符订阅（`"*"` 可当 `on_all` 用）、同步/异步插件方法统一调度；
- 接口已按冻结流程文档化（`docs/architecture.md`、`core_api.md`、`maintenance.md`）。

### 2.2 YingPet-v4（迁移源，架构上"半成品同路人"）

v4 已经完成了"核心冻结、功能全模组化"的重构，与规划书的目标架构高度同构：

| 层 | 现状 | LOC | 与目标的差距 |
|---|---|---|---|
| core/ | 自制迷你内核：EventBus/Registry/ActionRegistry/RuleEngine+safe_eval/FeatureContext/Harness/热重载 | 2,182 | 不是 Anima 内核；UI（window/animator/bubble/theme）混在 core 里 |
| mods/ | card.ying 角色卡 + 9 个功能插件（chat/settings/charcard/weather/todo/packer/sysmon/clock/hello）+ 3 套皮肤 + 全局行为 | 3,458 | 插件契约是 `FeatureContext` 白名单而非 `Plugin` ABC |
| tests/ | offscreen 模式 Qt 测试 6 个文件 | 859 | 需改写到新内核 API |
| 并发模型 | **纯同步 Qt**（QTimer/QThread），全工程无 asyncio | - | 与 async-first 的 Anima 内核需要对桥 |
| 依赖 | requirements.txt 只有 `PyQt6>=6.6`；**requests 实际被用但未声明** | - | 需补齐 |

### 2.3 AnimaPet 目录（`AnimaPet`）

盘点时**仅有规划书 .txt**，`PLAN.md` 是本目录的第一个项目文件。

### 2.4 结论（原文）

> 迁移 = ①把 YingPet 的 core/ 拆解为"Anima 内核（外购）+ 官方插件 + 渲染层"，②把 mods/ 的 FeatureContext 插件改写为 `anima.core.Plugin` 契约，③数据格式平滑迁移。大量代码是**搬运改写**而非重写。

---

## 3. 目录结构（目标结构 + 实际目录地图）

### 3.1 目标目录结构（2026-08-18 计划，`PLAN.md` §二）

```
AnimaPet\
├── main.py                      # 入口：单实例锁 + Qt + 内核启动 + PetWindow
├── run.bat                      # pythonw 启动器（沿用 YingPet 的 venv 探测链）
├── pyproject.toml               # 含 dev 依赖组
├── requirements.txt             # PyQt6, pydantic, requests（显式声明）
│
├── anima/
│   ├── core/                    # ★ Anima 内核 v1.1（自 work/ 复制，冻结接口）
│   │   └── (9 个模块，735 行，不改业务)
│   │
│   ├── plugins/                 # ★ 官方插件（规划书 §2.3 的 11 个）
│   │   ├── config.py            # core.config：JSON 读写、点路径分层读取、原子保存
│   │   ├── state.py             # core.state：状态漏斗、state.changed 广播、持久化
│   │   ├── actions.py           # core.actions：动作注册中心 + state_inc/set/emit
│   │   ├── bridge.py            # core.bridge：持有 PetWindow，注册 say/emote/anim
│   │   ├── loader.py            # core.loader：mods/ 扫描、8 类模组、card 展开
│   │   ├── hotreload.py         # core.hotreload：QFileSystemWatcher + 防抖重载
│   │   ├── rule_engine.py       # core.rule_engine：when/if/cooldown/then + safe_eval
│   │   ├── character_manager.py # core.character_manager：角色卡生命周期、归属过滤
│   │   ├── chat.py              # core.chat：聊天面板、LLM 适配器、历史管理
│   │   └── module_manager.py    # core.module_manager：启用/禁用、菜单、设置对话框
│   │
│   ├── adapters/                # LLM 适配器（chat 插件的服务实现）
│   │   ├── base.py              # LLMProvider 抽象：chat(messages, config) -> Reply
│   │   └── openai_compat.py     # OpenAI 兼容（DeepSeek/OpenAI/任意 base_url）
│   │
│   ├── models/                  # Pydantic v2 校验层（不进内核）
│   │   ├── config.py            # AppConfig（api/window/mods/debug）
│   │   ├── character.py         # CharacterCard / Expression / Animation
│   │   ├── mod.py               # ModManifest（8 种 type）
│   │   └── chat.py              # ChatMessage / ChatHistory
│   │
│   ├── utils/                   # jsonio(原子写+浅合并) / paths / log / theme
│   │
│   └── window/                  # 渲染层（PyQt6，仅被 bridge 持有）
│       ├── pet_window.py        # ← core/window.py（337 行）
│       ├── animator.py          # ← core/animator.py（180 行）
│       ├── bubble.py            # ← core/bubble.py（97 行）
│       ├── chat_panel.py        # ← mods/feature.chat/chat_panel.py
│       ├── dialogs/             # settings/charcard 对话框（← feature.settings/charcard）
│       └── tray.py              # ★ 新增：系统托盘（YingPet 没有）
│
├── mods/                        # 用户模组（沿用 YingPet 数据结构，见 §五）
│   ├── card.ying/               # 角色卡（anims/frames + images + emotes/idle/behaviors.json）
│   ├── behavior.health/
│   ├── feature.{weather,todo,packer,sysmon,clock,hello}/
│   └── ui.{default,dark,sakura}/
│
├── data/                        # 运行时数据（config.json / state.json / chat_history/）
├── tests/
│   ├── test_core/               # ← work/ 的 104 个内核测试原样搬入
│   ├── test_plugins/            # 改写的 YingPet 测试 + 新插件测试
│   └── integration/             # 启动→加载→交互→停止 全链路
├── tools/migrate_yingpet.py     # 数据/模组一次性迁移脚本
└── docs/                        # architecture / core_api / maintenance / plugin_dev_guide
```

### 3.2 实际目录地图（Phase 3 之后，2026-08-30 口径，`HANDOVER.md` §四）

> 📌 **这是历史快照，不是当前状态。** 归档整理时已发生的变化：根目录的
> `HANDOVER.md` / `PLAN.md` / `内核更换说明.md` 已不存在（前两者并入本文档，
> 第三者改名为 `docs/kernel_upgrade.md`）；`check_kernel_rules.py` 从根目录移入
> `tools/`；`anima/core` 已由 v1.1.1 升到 **v1.3.1**（含新增 `log.py`）；
> `dist/` 与 `build/` 已作为可再生产物清理。当前目录见 `README.md`。

```
AnimaPet\
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

> 注意：这张 08-30 地图里的 `tests\ 263 个` 与同一文档 §一 的 `268 passed` 口径不一致（原文未解释，见附录 A）。

---

## 4. 关键技术决策 TD1–TD6 与相关约定

（源：`PLAN.md` §三，2026-08-18；其中 TD1/TD3/TD4 的落地结论另见 `docs/PROJECT_STATUS.md` §3）

### 4.1 TD1 事件循环整合（最大风险点，已定方案）

YingPet 是纯同步 Qt；Anima 内核是 async-first。**推荐方案 A**：

**A（推荐，即 TD1-A）：内核 asyncio 循环跑在后台守护线程，Qt 占主线程**

- `main.py`：Qt 主线程照常 `app.exec()`；内核循环 `asyncio.new_event_loop()` 在 daemon 线程启动，`run_coroutine_threadsafe(app.start(plugins), loop)` 驱动生命周期。
- **UI 线程规则（写入 `plugin_dev_guide`，强制）**：
  1. `PetWindow`/对话框等 QWidget **只能在 Qt 主线程创建与访问**——由 bridge 插件在 Qt 线程（`main.py` 里先建窗口再 start）持有；
  2. 后台线程/协程要更新 UI，一律 `bridge.run_on_ui(fn)`（内部 `QMetaObject.invokeMethod` 队列）或发总线事件由 Qt 线程订阅者处理；
  3. 同步 `bus.emit` 从任意线程调用是安全的（内核数据结构无 await 临界区），规划书的事件流（click → rule → action → bridge → UI）全走同步 emit，天然落在 Qt 线程。
- 优点：零新增依赖、qasync 的边界问题全部避开、线程归属清晰。
- 代价：插件作者需理解两条线程规则（用 bridge API 封装后基本无感）。

**B（备选，即 TD1-B）**：qasync 统一循环。规划书风险表提到的原方案，模型更简单（单线程、可 await），但引入新依赖且与 PyQt6 版本偶有兼容问题。若 A 在集成测试暴露难以解决的时序问题，切换到 B 的改动集中在 bridge 与 `main.py`。

**落地结论（`PROJECT_STATUS.md` §3.1，2026-08-23）**：

- Qt 占主线程，Anima asyncio 内核跑在后台 daemon 线程；
- `bridge.run_on_ui` 是**唯一合法跨线程 UI 通道**；
- 功能模组白名单新增 `ctx.task` / `ctx.run_on_ui` / `ctx.use`，确保第三方也能写 UI + 异步插件。

### 4.2 TD2 内核小版本升级 v1.0 → v1.1（走冻结变更流程）

迁移暴露的内核缺口，按 `maintenance.md` 的流程补齐（均为**新增**，非破坏性）：

| 缺口 | 来源 | 方案 |
|---|---|---|
| `ctx.task(coro)` | 规划书 §2.2.2：任务卸载自动 cancel | `Context.task()` + `EffectTracker.push_task()`：注册即记录 cancel 回滚 |
| `bus.on_all` | RuleEngine 需要监听一切事件 | **不需要改**——`subscribe("*")` 已覆盖 |
| 类型形式 provide/use | 规划书 §6.3 `ctx.use(ConfigService)` | 插件层薄封装：类 → `f"{cls.__module__}.{cls.__qualname__}"` 字符串键，内核不动 |
| 线程安全 emit | TD1 的 Qt 线程调用 | 语义已满足；在 bus docstring 明确"单写多读、无 await 临界区"结论 |

升级在 `work/` 仓库完成（附测试、更新三份文档、`__version__ = "1.1"`），再同步复制到 AnimaPet；`work/` 保留为内核上游。

**后续（本文档之后）**：内嵌内核经 `ab239e9` 升到 v1.1.1，于 **2026-09-21**（提交 `0922f9b`）升到 **v1.3.1**。细节见 `docs/kernel_upgrade.md`。

### 4.3 TD3 Pydantic 只做边界校验

`models/` 用 Pydantic v2 校验 manifest/config/角色卡/聊天记录的**加载边界**（坏文件 → 明确错误 + 降级默认值，沿用 YingPet"绝不因坏数据崩溃"的原则）。内核与插件内部传参**不引入 Pydantic 类型**，避免渗透。

**落地后的校验边界分工（`HANDOVER.md` §三.1 + `PROJECT_STATUS.md` §3.2）**：

- `anima.models.load_card/save_card` = **整体校验**（编辑器/工具保存把关，坏数据报 `ValueError` 带文件名）；
- `loader._build_card` = **逐文件降级**（运行期：坏表情/规则/台词段丢弃记日志，其余照常，绝不因坏数据崩）。
- 测试两套语义都有覆盖。

### 4.4 TD4 角色卡格式：YingPet `card.*` 规范化为 `.chara`

YingPet 的 `card.ying/` 结构（manifest + emotes.json + idle.json + behaviors.json + anims/frames + images）经过实测，规划书的 `.chara` manifest（附录 A）是它的**超集视图**。决策：

- **采用 YingPet 物理结构 + 规划书 manifest 字段**做统一格式；
- Pydantic 模型**双名字段兼容**（如 `expressions` ↔ `emotes.json`）；
- `tools/migrate_yingpet.py` 做一次性转换与校验；
- 帧动画沿用 **PNG 序列**（不引入 GIF/WebP 渲染路径，规划书 §3.3 的扩展留到 Phase 5+）。

**落地结论（`PROJECT_STATUS.md` §3.3）**：

- 物理结构 = YingPet `card.*` 文件夹 + `manifest.format="chara-1"`；
- 表情双名兼容（`emotes` ↔ `expressions`）；
- id 统一 `card.` 前缀 + 字符集归一；zip 导入带 **Zip-Slip 防护**。

### 4.5 TD5 LLM 适配器接口

YingPet 只有 OpenAI 兼容单适配器（DeepSeek 默认）。抽出：

- `LLMProvider` 抽象（`async chat(messages, config) -> Reply(emotion, text)`）；
- 首个实现 `openai_compat` **100% 复用**现有请求/解析逻辑（含 emotion 白名单校验、降级策略）；
- `requests` 显式进 requirements；
- QThread 改为 `asyncio.to_thread` 包同步调用（留在内核线程池，不碰 UI 线程）。

### 4.6 TD6 工程与运行时约定

- **依赖**：`PyQt6>=6.6`、`pydantic>=2`、`requests`；dev：`pytest / pytest-asyncio / pytest-cov`。AnimaPet 建独立 `.venv`。
- **保留 YingPet 的工程韧性**：单实例 Win32 互斥锁、`pythonw` + 原生 MessageBox 的致命错误通道、`sys.excepthook` 不退出的最后防线、`QT_QPA_PLATFORM=offscreen` 测试模式。
- **事件命名**沿用规划书 §6.2（`域.对象.动作`），YingPet 事件名（`user.click`、`chat.reply`、`timer.sit` 等）已在迁移映射表中逐一对齐。
- **Git**：AnimaPet 新仓库，按里程碑提交（沿用 `work/` 的 conventional commits）。

### 4.7 方案 A："一切皆插件"的最后一块拼图

（源：`docs/PROJECT_STATUS.md` §3.4）

- 角色卡管理器、聊天窗口从"框架硬编码"下放为 `mods/feature.charcard/`、`mods/feature.chat/`；
- 总管理器（module_manager）现在能对它们**启停、删除、替换**；
- 新增「模组管理 → 新建… → 新建功能模组…」，用户可从 UI 创建自定义模组。

---

## 5. 迁移映射表（原文标注为"核心干货"）

（源：`PLAN.md` §四，标题原文即"迁移映射表（核心干货：YingPet → AnimaPet）"）

| YingPet-v4 文件 | LOC | 去向 | 改写要点 |
|---|---|---|---|
| core/events.py | 59 | **删除**，用内核 EventBus | 20 个 EventNames 常量 → `anima/events.py`（纯常量表）；`on_all` → `subscribe("*")` |
| core/actions.py | 30 | anima/plugins/actions.py | 包成 Plugin；服务名 `actions`；内置 state_inc/set/emit 改调 state 插件服务 |
| core/registry.py | 132 | anima/plugins/loader.py + character_manager.py | 类型化 OrderedDict 注册表成为 loader 提供的服务；角色归属过滤逻辑进 character_manager |
| core/loader.py | 404 | anima/plugins/loader.py | 扫描/8 类模组/card 展开/帧缓存原样保留；产出改写入自己的注册表服务并 `ctx.provide("mods")` |
| core/rule_engine.py | 156 | anima/plugins/rule_engine.py | `bus.on_all` → `bus.subscribe("*")`；动作执行改走 actions 服务；`@idle.this` 模板保留 |
| core/safe_eval.py | 248 | anima/plugins/rule_engine.py（同包模块） | **原样搬运**（含测试），零改动 |
| core/features.py | 167 | **删除** | FeatureContext 白名单由内核 Context + Plugin ABC 取代；菜单注册改 `module_manager` 服务 |
| core/harness.py | 250 | 拆解：main.py + config/state 插件 | DEFAULT_CONFIG → config 插件；change_state → state 插件；watcher 编排 → hotreload 插件 |
| core/window.py | 337 | anima/window/pet_window.py | 事件改 emit 内核总线；`say/set_emotion/play_anim` 由 bridge 注册为动作；右键菜单数据源改 module_manager |
| core/animator.py | 180 | anima/window/animator.py | 基本原样（QTimer 帧状态机与内核无关） |
| core/bubble.py | 97 | anima/window/bubble.py | 原样 |
| core/theme.py | 44 | anima/utils/theme.py | 原样 |
| core/jsonio.py / paths.py / log.py | 70 | anima/utils/ | 原样（原子写、冻结路径感知、日志） |
| mods/feature.chat/* | 753 | plugins/chat.py + window/chat_panel.py + adapters/ | 拆三块：面板（UI 层）、插件（编排）、适配器（openai_compat）；QThread → to_thread；历史按 `data/chat_history/<card>/<conv>.json` 分角色存储（规划书 3.6） |
| mods/feature.settings/* | 598 | plugins/module_manager.py + window/dialogs/ | ModsDialog 的启用树改走 lifecycle enable/disable；SettingsDialog 编辑 config 服务 |
| mods/feature.charcard/* | 1,273 | window/dialogs/charcard/ + character_manager | 编辑器 GUI 基本原样；保存目标改 .chara 新格式（Pydantic 校验） |
| mods/feature.{weather,todo,sysmon,clock,hello,packer} | ~834 | mods/ 同名（用户模组层） | FeatureContext API → Plugin+Context API：`ctx.emit/on` 同名保留；`ctx.say/emote` → `use("bridge").say/emote`；`ctx.get/set_state` → `use("state")`；`ctx.add_menu_action` → `use("module_manager").add_menu`；QThread 采样器保留 |
| mods/card.ying、behavior.health、ui.* | ~560 | mods/ 原样 + tools 转换 | 行为/皮肤 JSON 兼容；card 增补 manifest 新字段（工具自动） |
| tests/* | 859 | tests/test_plugins/ + integration/ | 断言从 Harness/FeatureContext 改为内核 API；offscreen 模式保留 |
| main.py | 81 | main.py | 保留单实例锁/异常通道；启动序改为：Qt → 内核线程 → App.start(官方插件) → PetWindow → bind |
| tools/migrate_v3_to_card.py | 101 | 删除 | 历史工具，v4 已消费 |

### 5.1 改写量估算（原文）

- **原样/近原样搬运 ~2,600 行**（utils/window/animator/bubble/safe_eval/皮肤与数据模组/功能模组小改）；
- **需实质改写 ~1,700 行**（harness 拆解、loader/rule_engine 契约化、chat 拆分、settings/charcard 对接）；
- **新写 ~800 行**（bridge、11 个插件壳与编排、tray、adapters、迁移工具、main.py 新启动序）。

---

## 6. 风险与对策（2026-08-18 立项口径）

（源：`PLAN.md` §六）

| 风险 | 等级 | 对策 |
|---|---|---|
| Qt 主线程与内核线程时序冲突（TD1-A） | 高 | bridge 强制 UI 线程规则；集成测试覆盖"协程回调更新 UI"路径；预案 qasync（TD1-B，改动面小） |
| 热重载半途失败留下脏状态 | 中 | 内核 unload 已保证"异常聚合但状态推进"；hotreload 对失败模组自动回禁用并冒泡提示 |
| 聊天/天气 QThread → async 改写引入回归 | 中 | 先 `to_thread` 包同步代码（行为等价），异步化推迟到 Phase 4 |
| 数据迁移破坏老用户数据 | 中 | 迁移工具只增不改原文件；写前备份到 `data/backup/`；YingPet 原目录只读 |
| 功能对等遗漏 | 中 | Phase 2 建立"对等清单"（以 YingPet 使用说明书 486 行为基准）逐项验收 |
| 内核升级 v1.1 破坏冻结 | 低 | 仅新增接口；work/ 走完整变更流程（评审 = 本计划 TD2 表） |
| 工期 | - | 每阶段独立可运行，可随时收缩到 Phase 2 止（已达成功能对等） |

---

## 7. 里程碑与阶段完成情况（三份文档进度表合并）

> 本节把三份文档里反复出现的"Phase 0-5 ✅ 完成 / tag v1.0"合并为一张总表（原文各自展开的逐项勾选清单已压缩），并单列一张"技术要点"保留其中的实质信息。

### 7.1 里程碑总览（`PLAN.md` §七）

| 阶段 | 交付物 | 预估 | 出口标准 |
|---|---|---|---|
| P0 | 内核 v1.1 + 仓库骨架 | 0.5 周 | 测试全绿 + 铁律检查通过 |
| P1 | 最小可运行宠物 | 1 周 | main.py 启动，角色显示与基础交互 |
| P2 | 全功能对等 | 1.5 周 | 对等清单 100%，热重载可用 |
| P3 | .chara 规范 | 1 周 | 拖装角色、编辑器、多角色隔离 |
| P4 | 多 LLM 聊天 | 1 周 | 适配器可切换、历史可导出 |
| P5 | 生态与分发 | 1 周 | 打包 exe + 开发者指南 + v1.0 tag |

合计 **6 周等效**（对照规划书原 12 周：内核已完成 + 代码可搬运，压缩一半）。
原计划的立项范围文字：规划书 12 周路线图的 Phase 0 已由 `work/` 内核完成；YingPet 代码可复用度高，整体压缩到 **6 个阶段 / 约 6-7 周等效工作量**，每阶段以"验收可运行"收口。

### 7.2 六阶段完成情况（合并快照）

| 阶段 | 完成情况 | 当时的验收结论 |
|---|---|---|
| Phase 0 | ✅ 完成 | `pytest tests/ -v` 全绿；`check_kernel_rules.py` 通过 |
| Phase 1 | ✅ 完成 | `python main.py` 启动、ying 待机动画正常、点击/拖拽/双击到总线、右键菜单可 emote/退出、行为规则（petted 加好感）触发。**offscreen 冒烟实测通过**：20 模组对象 0 错误、规则 7 事件订阅、角色帧加载；**真机 GUI 交互当时待用户环境双击验收** |
| Phase 2 | ✅ 完成 | 与 YingPet-v4 功能对等清单逐项打勾（角色/行为/天气/待办/时钟/系统监控/打包导入导出/设置 ✅；角色卡编辑→Phase 3、聊天→Phase 4）；拖入新模组 ≤1 秒热生效；卸载模组后 bus/registry 无残留（集成测试断言 `bus.count()==0`） |
| Phase 3 | ✅ 完成 | 拖入 .chara 文件夹或 zip 安装新角色无需重启（offscreen 测试覆盖安装+重扫可见）；坏 manifest 报错明确且应用不崩（整体校验/逐文件降级两套测试齐全）；角色切换后人设/行为/历史完全隔离。**真机拖装/切换隔离仍在第 5 步用户环境冒烟** |
| Phase 4 | ✅ 完成（代码+测试） | DeepSeek/OpenAI 任意 base_url 配置即用（适配器单测覆盖缺 key 降级）；对话中角色表情随 emotion 字段切换；聊天记录可按 txt/JSON 导出导入；断网/坏 key 得到角色内错误回复。**真机 LLM 联调待用户环境** |
| Phase 5 | ✅ 完成 | 第三方开发者按指南可写出并热加载插件；打包 exe 已构建并 offscreen 冒烟；启动 1.520s 达标（<3s）；内存真机对比待用户 |

**tag v1.0 已打**（Phase 5 收尾时打）。

### 7.3 各阶段值得留存的技术要点

（从 `PLAN.md` §五 的逐阶段记录中提炼，去掉重复的勾选表）

- **Phase 0**：`work/` 内核升级 v1.1 = `ctx.task()` + `EffectTracker.push_task()`（含测试与文档更新）；AnimaPet 建仓：目录骨架、pyproject、venv、内核与 `test_core` 复制；冒烟 `asyncio.run(App().start([]))` 通过。
- **Phase 1**：落地顺序为 utils/events → config → state → actions → window 层搬运（去 harness 引用）→ **bridge 插件（本阶段最难，TD1 落地）**：Qt 主线程持有 PetWindow、`run_on_ui` 封装、注册 say/emote/anim 动作、功能菜单登记 → loader（先支持 card + ui + behavior 只读扫描）→ `main.py`（单实例锁 → Qt → 内核线程 → start → card.ying 显示）→ 集成测试。
- **Phase 2**：
  - **hotreload**：QFileSystemWatcher + **800ms 防抖** → 经 `module_manager.rescan`（线程感知调度到内核循环，注册表重建无竞态）；watcher 是 QObject，经 `bridge.run_on_ui` 保证在 Qt 主线程创建；`_feature_data` 等价物 = `module_manager.feature_data(id)`（热重载状态不丢）。
  - **rule_engine**：safe_eval 原样搬运 + 规则/动作/模板全量回归。**踩到的语义差异**：内核通配订阅 `"*"` 的 handler 收不到事件名 → 改为按规则声明的事件名逐个订阅（语义与 on_all+过滤等价，订阅随 `mods.reloaded` 重建）；**后续优化方向**：事件分发索引 + 每事件一次快照。
  - **character_manager**：card 生命周期、active 切换、归属过滤，`character.switch` → 窗口刷新 → `character.switched` 事件链（功能模组可经 `use("character_manager").switch(id)` 程序化切换）。
  - **module_manager**：启用/禁用持久化到 `config.mods.enabled`、菜单注册服务、ModsDialog/SettingsDialog 对接 lifecycle；**feature 适配器强制 `dependencies=[]`，禁用 = 完整卸载、再启用 = 全新实例重新 on_load**。
  - 六个功能模组（weather/todo/sysmon/clock/hello/packer）：FeatureContext 白名单契约与 YingPet **同名平移**（仅 import 改 anima；packer 纯函数复用 `anima.mods.packer`）；设置对话框并入 module_manager（API / 人设写回角色卡 manifest）。
  - `tools/migrate_yingpet.py`：config/state/chat_history 平移 + 字段补齐（默认结构合并、未知键留 `_legacy`、功能模组状态随 state 平移、写前备份 `data/backup/`、源目录只读、`--dry-run`）。
- **Phase 3**：Pydantic 模型 + JSON Schema 导出（`docs/schema/chara.schema.json`，由 `tools/export_chara_schema.py` 生成，**测试断言无漂移**）；`docs/chara_format.md` + migrate `export-chara`/`import-chara`（`card.*` ↔ `.chara` 互转）；charcard 编辑器 6 页签 GUI 平移到 `anima/window/dialogs/charcard/`（dialog/wizard/assets），保存统一过 `anima.models.load_card` 整体预检；多角色并存与切换上下文隔离：聊天历史按角色分目录 `data/characters/<id>/chat_history.json`（迁移工具按当前角色分流）；ZIP 形式 `.chara` 加载：packer 扩展 + id/类型归一（`chara`→`card`、补 `card.` 前缀），Zip-Slip 防护复用。
- **Phase 4**：`LLMProvider` 抽象 + `openai_compat`（async 抽象 + sync requests 包 `to_thread`，解析/降级复用）；chat 插件 + `window/chat_panel.py`（system prompt 注入人设 + emotion 白名单；`stream: bool` 配置已预留在 DEFAULT_CONFIG，**流式打字机渲染后续实现**）；历史分角色/分会话存储、搜索、单条删除（`HistoryStore.delete_message/delete_conversation`）、JSON 导入导出；API key 仍存本地 config（`config.json api.api_key`；适配器缺 key/坏 key 降级为角色内错误回复）。
- **Phase 5**：**tray（新增）** `anima/window/tray.py` + main.py 接入（角色/皮肤/退出）；`docs/plugin_dev_guide.md`（Hello World、Context API、**两条线程规则**、打包规范）+ `tools/new_plugin.py` 脚手架；PyInstaller 打包 `build.spec` + `tools/build_exe.py`，成功构建 `dist/AnimaPet/`，offscreen 冒烟存活 8s；性能回归 `tools/benchmark.py` 实测**启动 1.520s / Python 峰值 6.5 MiB（offscreen，2026-08-23 口径）**，真机内存对比待用户；`README.md` + 功能对等/进度说明；tag v1.0。

### 7.4 Phase 3 五项子任务核对（2026-08-23 口径，`HANDOVER.md` §一）

| # | PLAN 子任务 | 状态 |
|---|---|---|
| 1 | Pydantic 模型 + JSON Schema 导出 | ✅ 完成（`anima/models/` + `docs/schema/chara.schema.json`，漂移测试） |
| 2 | 格式规范文档 + 迁移工具 card.* ↔ .chara 互转 | ✅ 完成（`docs/chara_format.md` + `export-chara`/`import-chara`） |
| 3 | charcard 编辑器 6 页签 GUI + Pydantic 校验 | ✅ 完成（`anima/window/dialogs/charcard/`，菜单接入 module_manager） |
| 4 | 多角色并存与切换上下文隔离 | ✅ 完成（`character_manager.history_dir` + 迁移按角色分流） |
| 5 | ZIP 形式 .chara 加载（packer 防护复用） | ✅ 完成（packer 扩展 + id/类型归一） |

Phase 4 四项子任务已全部完成：`anima/adapters/`（LLMProvider/openai_compat）、`anima/plugins/chat.py` + `window/chat_panel.py`、按角色历史存储（搜索/单条删除/JSON 导入导出）、`stream` 配置预留。

### 7.5 遗留：真机冒烟（截至 2026-08-30 的下一步）

（源：`HANDOVER.md` §五）

> **第 0 步（提交）和第 7 步（修 🟡）已于 2026-08-30 完成**，现在只剩用户真机冒烟。

- **第 5 步（真机冒烟，用户环境）**：按 `docs/RELEASE_CHECKLIST.md` 逐项验证；确认稳定后删除 `<本地归档目录>/core` 归档。
- **第 6 步（真机冒烟，用户环境）**：重启应用 → 拖入 .chara zip 新角色 → 角色切换后人设/行为/历史完全隔离 → 编辑器改人设即热生效 → 聊天窗收发/导出。
- 提醒：**用户真机实例一直是旧代码**，所有 Phase 3/4、08-28、08-30 功能都要重启后才可见。08-30 已重新打包（`dist/AnimaPet`，155MB）并冒烟通过，可直接拿去真机验证。若冒烟发现问题，回来改代码后补测试并重新提交。

**冒烟时请重点看这几处（都是当时动过、且改了行为的）**：

| 位置 | 看什么 |
|---|---|
| 角色卡管理器·行为页签 | 改一条带 `after_ms` 的动作，保存后 JSON 里延时还在 |
| 设置/模组管理/角色卡/皮肤工坊 四个对话框 | 切到「樱粉」皮肤后对话框应随之变浅（不再是深紫） |
| 模组管理 → 导入 GIF 动画 | 故意导一个坏 GIF，失败后 `mods/` 下不留 `anim.*` 空目录 |
| 聊天 → 备份▾ → 从 JSON 恢复（合并） | 同一份备份连合两次，消息不该翻倍 |
| 桌宠本体 | 切换尺寸/皮肤、播放表情动画都正常（帧缓存 LRU 新增） |

---

## 8. 最终交付物与未完成/未验证（2026-08-23 结项口径）

（源：`docs/PROJECT_STATUS.md` §2）

| 交付物 | 状态 |
|---|---|
| Anima 内核 v1.1.1（840 行纯标准库，冻结） | ✅ |
| PLAN Phase 0-5 全部代码 | ✅ |
| 自动化测试 | ✅ 254 passed（结项当日口径，见附录 A） |
| 角色卡 `.chara` 格式 + JSON Schema + 编辑器 | ✅ |
| 聊天与多 LLM（OpenAI/DeepSeek 兼容） | ✅ 代码完成，真机联调未做 |
| 系统托盘、日志导出、新建功能模组入口 | ✅ |
| 开发/使用文档 | ✅ 4 份指南 + 结项报告 |
| PyInstaller 打包 | ✅ `dist/AnimaPet/AnimaPet.exe`（onedir，含 mods） |
| Git tag | ✅ `v1.0` |

**未完成/未验证**（原文四项）：

- 真机持续使用验证（用户侧）未进行；
- 聊天 API 实际联网联调未做（依赖 API key 与网络）；
- exe 无自定义图标/版本信息/单文件版；
- 性能内存与 YingPet 实测对比未做（offscreen 启动 1.520s / Python 峰值 6.5 MiB，2026-08-23 口径）。

---

## 9. 项目规模与提交时间线

### 9.1 项目规模（`docs/PROJECT_STATUS.md` §4，2026-08-23 口径）

```text
anima/           框架（内核/插件/模型/适配器/窗口）
mods/            11 个功能模组 + 角色卡 + 3 皮肤（含内置 feature.chat/charcard）
docs/            使用/开发/.chara/发布清单/结项报告
tools/           迁移/schema/脚手架/打包/benchmark
tests/           254 个测试（内核/插件/集成）
dist/            打包产物（gitignore，不入库）
```

（08-30 之后 mods 规模变化：素材统一最长边 512、共 89MB；`dist/AnimaPet` 155MB。见 §17。）

### 9.2 提交时间线（合并 `PROJECT_STATUS.md` §4"提交链（简）"、`HANDOVER.md` §二 与逐提交内容索引）

**结项前（Phase 0 → tag v1.0）**：

```text
8c8a899 Phase 0 建仓
…                Phase 1/2 基础设施与插件化（未逐条记录）
ab239e9 内核升级 v1.1.0 -> v1.1.1（失败回滚/重启安全）
6617f5e Phase 3 角色卡模型层——Pydantic 模型/schema/.chara 包/按角色隔离
380b8df Phase 3 角色卡编辑器 GUI + 测试 + .chara 格式文档
b7f56ef Phase 4 聊天与多 LLM——适配器/chat 面板/按角色历史/JSON 导入导出
e7744af Phase 5 部分——系统托盘/开发指南/脚手架/README
e5ac527 方案 A——角色卡管理器/聊天窗口下放为内置功能模组，总管理器可启停/替换
244bd8e 模组管理新增「新建功能模组…」入口
d35e9d4 Phase 5 收尾——PyInstaller 打包/性能基准/README 回填
bc0107e 模组管理日志导出/打开日志文件夹
48993ad HANDOVER v10 + 发布前真机冒烟清单
a8672c1 插件开发指南/.chara 开发指南/整体使用指南
4f5b43d 项目结项报告 PROJECT_STATUS.md（2026-08-23）
tag: v1.0
```

> 结项前这套链里另有若干补救/经验提交未列入上面的"简"链，例如 `1feb486`（HANDOVER 补真机反馈修复经验：`quitOnLastWindowClosed`/`Task.result`/删除入口）、`120bc07`（关闭辅助窗口不再退出宠物 + ModsDialog 删除功能）、`94ca431`（ui 皮肤测试改写 + 真实数据对等回归）、`8a6eb8a` / `fbc864e`（A 档三项修复：loop 注入、跨线程 rescan 调度、规则引擎事件索引）。原文只给了"简"链，此处按 git 记录补记，供追溯。

**2026-08-28 / 08-30 两批（结项后追加，全部已提交，工作区干净）**：

```text
377e878 2026-08-30 feat+refactor+perf: UI 统一主题/对话框去重/新手四功能 + 内存与解码优化
caae6b0 2026-08-30 perf: 素材降至最长边 512；打包剔除 32MB 冗余；补瘦身工具与文档
48c67b0 2026-08-30 fix: 行为规则编辑器不再静默丢字段（after_ms / if / on 列表 / 高级动作）
8a56b04 2026-08-30 fix: 对话框跟随皮肤；导入失败回滚目录；合并导入去重文件内重复   <-- 当时 HEAD
4b7151b 2026-08-30 docs: HANDOVER v12——两批改动已提交、4 项审查问题已修复
0922f9b 2026-09-21 chore(kernel): 内嵌内核 v1.1.1 -> v1.3.1（含 ctx 保留名修复与内核测试同步）
```

> `4b7151b`、`0922f9b` 及以下内容已超出三份源文档的记述范围，按仓库 git 记录补记。

**提交内容索引（`HANDOVER.md` §二，压缩为一行一项）**：

| 提交 | 内容一句话 |
|---|---|
| `377e878` | 08-28 批次 A（UI/可维护性重构）+ 08-30 批次 B（性能/新手功能）的**全部 Python 代码与测试**；含 chat 历史导入三选、GIF 导入到卡内、行为规则可视化编辑器、`dialogs/common.py`（新增）、`dialogs/skinmaker.py`（新增）、`mods/feature.skinmaker/`（新增）、modmanager 新建对话框合并基类、settings 两步向导 + 温度滑条、pet_window/tray 菜单拆分、`load_scaled_pixmap` + 全局帧 LRU、Animator 解码即缩放与定时器按需启停、气泡跟随主题字体、`theme.py` 重写（推导键/保色相提亮/亮度自适应描边）、`.gitignore` 补 `.workbuddy/` |
| `caae6b0` | `mods/card.ying/**/*.png` 236 张降到最长边 512（187MB → 89MB，**是修改不是删除**，全部在 git 里，`git checkout -- mods/` 可完整回滚）；`build.spec` 剔除 `opengl32sw`/`Qt6Pdf`/`Qt6Network`/非 `zh_CN` `.qm`（−32MB）；`tools/optimize_assets.py`（新增，默认预览、`--apply` 写盘）；`docs/` 补 `PROJECT_STATUS` §9/§10、`user_guide`、`ui-preview.png` |
| `48c67b0` | 🟡1 行为规则编辑器不再静默丢字段（`after_ms`/`if`/`on` 列表/高级动作） |
| `8a56b04` | 🟡2 对话框跟随皮肤；🟡3 导入失败回滚目录；🟡4 合并导入去重文件内重复 |

### 9.3 关于提交切分：为什么没按"批次 A / 批次 B"拆

（源：`HANDOVER.md` §二，属可复用的工程经验）

原计划按批次拆，但两批在 **`anima/window/animator.py` 和 `anima/window/chat_panel.py`** 两个文件里纠缠（A 改定时器与批量渲染，B 改解码即缩放与气泡 HTML），而 git 的最小粒度是文件 —— 强行拆开必然产出一个"编译不过或测试挂掉"的中间提交。

所以改成按**能否独立通过测试**切分：

- `377e878` 全部 Python 代码与测试（两批合一，提交后测试通过）；
- `caae6b0` 素材 + 打包 + 文档（已确认无测试断言素材尺寸或 `build.spec` 内容）。

---

## 10. 重要澄清与设计决策（勿偏离）

（源：`HANDOVER.md` §三，2026-08-30 口径；这是三份文档中唯一一处系统列出"接手者不许偏离的约定"的地方，**逐条保留**）

1. **校验边界分工**：`anima.models.load_card/save_card` = 整体校验（编辑器/工具保存把关，坏数据报 `ValueError` 带文件名）；`loader._build_card` = 逐文件降级（坏表情/规则/台词段丢弃记日志，其余照常）。测试两套语义都有覆盖。
2. **.chara 包格式**：物理结构 = YingPet `card.*` 文件夹 + `manifest.format="chara-1"`；zip 打包经 `packer.export_mod`，导入走 `packer.import_mod_zip`（Zip-Slip 防护）；`type="chara"` 装完必须回写 `type="card"` + id 补 `card.` 前缀。
3. **Behavior.on 必填非空**；rule_engine 同时支持 `when` 和 `if`，模型 `extra=ignore` 只校验不裁剪，规则原文透传。
4. **编辑器保存语义**：人设/动画/台词/行为/表情页签改 `raw` dict 原样回写到 `source_file`，但保存前整体预检（`load_card`）；新建向导生成自包含卡。
5. **其余沿用第 6 版**：TD1 双线程、QObject 亲和性、feature 禁用 = 完整卸载、jsonio 路径安全、`main.py` 互斥量在 `main()` 里。
6. **素材格式必须是 PNG，不许换**（08-30 新增，用户明确要求）：用户会自制 mod，换 WebP 会直接破坏第三方生态。同理，**帧数、文件命名、动画时序、manifest 引用方式**都不许动 —— 降采样/重编码是唯一允许的优化手段。
7. **图片一律走 `load_scaled_pixmap`，禁止 `QPixmap(path).scaled(...)`**（08-30）：后者会先把 2048² 的表情图解成 16MB 位图再缩小，桌宠只用得到 320px。
8. **主题键的推导契约**（08-30）：皮肤只定义 14 个基础键，其余由 `_derive()` 补齐，**显式定义优先**。`DEFAULT_THEME` 里带推导性质的键必须等于 `_derive()` 对主色的计算结果，否则会躺着永远用不到的死值（`tests/test_utils.py::test_theme_merge_none_safe` 守这条）。
9. **断言配色时断言"回退到默认值"，不要写死色值**（08-30）：换配色时不该动测试。
10. **可视化编辑器必须保证往返保真**（08-30）：表单只读得懂一部分字段时，读不懂的要原样带回，不能整体重建 dict。规则/动作的 JSON 是用户能手写的，编辑器只是它的一个视图 —— 见过即必须保留。新增的「原样保留」分支优于"静默降级"。
11. **对话框等临时窗口构造时取一次当前皮肤即可**（08-30），不必做热更新；常驻窗口（`PetWindow`）才需要 `_apply_skin` 跟着热重载走。

---

## 11. 踩过的坑与经验

### 11.1 迁移期（源：`docs/PROJECT_STATUS.md` §5，2026-08-23）

1. **packer 归一分支**：`chara→card` 类型/id 归一在无目录冲突时不会回写 manifest，需用 `raw_id` 比较并强制回写；
2. **migrate 历史分流**：`chat_history[<id>]` 计划项未按前缀匹配，被当字符串写坏；
3. **Qt 线程调 async**：UI 信号里不能 `asyncio.ensure_future`，统一走 `module_manager.fire`；
4. **FeatureContext 扩展**：官方功能下放为 mod 后，必须补 `task/run_on_ui/use` 白名单能力；
5. **配置注入时机**：测试里先 `cfg.set` 不落盘会被 `ConfigPlugin.load` 覆盖，要先 `cfg.save()`；
6. **Mimosa hook**：仓库内写文件走 `jsonio.save`（项目根白名单 + 原子写）。

### 11.2 会话交接记新增（源：`HANDOVER.md` §八，标注"本会话新增"）

- **packer 归一分支的坑**：`import_mod_zip` 里 `mod_id` 先归一为 `card.xxx` 后，`new_id != mod_id` 在无目录冲突时恒为 False，导致 `chara→card` 类型、id 前缀都没有回写 manifest（扫描仍报未知类型）。修复：用 `raw_id` 比较，`mtype=="chara"` 必须无条件回写。测试 `test_packer_import_chara_normalizes_type_and_id` 已覆盖。
  （与 §11.1 第 1 条是同一坑的两次记述。）
- **migrate chat_history 分流的坑**：计划项 kind 是 `chat_history[<id>]`，但复制分支只判断 `kind == "chat_history"`，导致按角色文件被当字符串写坏。修复：`kind.startswith("chat_history")`。测试 `test_migrate_chat_history_split_by_character` 已覆盖。
  （与 §11.1 第 2 条是同一坑的两次记述。）
- **命令行中文/`\n` 转义**：写测试脚本时字符串里的换行转义容易在 heredoc/模板字面量中被二次解释，务必用 `ast.parse` 或 repr 检查生成文件后再跑。
- **菜单断言**：module_manager 新增「角色卡管理器…」后，`test_module_manager` 的三处 `feature_menu` 断言已同步更新。
- **Mimosa hook / Jsonio**：仓库内写文件走 `jsonio.save`（项目根白名单 + 原子写），测试临时目录记得 monkeypatch `jsonio._BASE`。
  （与 §11.1 第 6 条是同一坑的两次记述。）
- **Qt 线程调 async 的坑**：chat 面板信号在 Qt 主线程，不能直接 `asyncio.ensure_future`（无运行循环）。统一走 `module_manager.fire(coro)`（跨线程投递内核循环；单线程测试回退 `create_task`）。
  （与 §11.1 第 3 条是同一坑的两次记述。）

### 11.3 2026-08-30 优化轮新增（源：`HANDOVER.md` §八）

- **测 Windows 进程内存要用 `PagefileUsage` 不是 `WorkingSetSize`**：后者复用已提交页，测不出瞬时峰值。且 `GetProcessMemoryInfo` 在 64 位下**必须显式声明 `restype`/`argtypes`**，否则进程句柄被截断成 32 位、静默返回 0（原文自述"我在这上面栽了两次，一直报 0.00MB"）。验证方法：分配并 touch 200MB，看增量是否精确等于 200.4MB。
- **浅色皮肤下"提亮"会变白底白边**：`_shade` 只会往亮走，浅色皮肤算出 `border=#fff7fa`。修法是 `_contrast_shade()` 按亮度自动翻转方向（`lum > 0.6` 则压暗）。
- **往白色插值会洗掉色相**：深紫 `#241a30` 直接往白提亮变成灰 `#87818d`。修法是 `_lighten()` 往"本色调到最亮的版本"插值；无彩色（纯灰/黑）的最亮版本恰好是白，自动退化，所以深色皮肤仍能拿到可见描边。
- **GIF 解帧的 600 帧上限是硬截断**：`common.py::extract_gif_frames`，超限时用户无感知，且不清理已建目录（原文指向"§十一 🟡3"，即本文档 §17.3 第 3 项）。
- **PyInstaller 重新打包会先 `rmtree dist/AnimaPet`**：想保住旧产物就先 `--distpath` 到暂存目录验证后再替换。另外本仓库的 `mv` 有时会撞上 Permission denied（安全删除机制拦截），改用 `cp -r` 再删源目录即可。

### 11.4 2026-08-30 修复轮新增（源：`HANDOVER.md` §八）

- **照着"观察到的行为"写断言，会把 bug 固化成契约**：`test_gif_import` 里 `assert mid2 == "anim.dance_2"` 写的就是 bug 本身（重名序号先自增，跳过 `_1`）。修完序号后这条测试挂了 —— 这是好事，说明它确实锁住了行为，但方向锁反了。**写断言时问一句"这是期望的行为，还是当前的实现？"**
- **补完测试必须验证它能抓到 bug**：临时把修复还原掉跑一遍，确认测试真的失败。本轮 5 条新测试全部这么验过（还原后分别报 `KeyError: 'after_ms'`、`['anim.broken'] == []`、`4 == 2`、QSS 残留默认前景色）。**测试在新旧代码下都通过 = 没测到东西。**
- **验证主题键名别想当然**：第一次写对话框皮肤验证脚本时用了 `text` 这个键，看着合理但项目里根本没这个键（真实皮肤用 `fg_panel`/`fg_browser`），结果 QSS 出现浅底浅字 `#fff5f8` + `#ece2f7`，差点误判成修复有 bug。验证前先 `cat mods/ui.sakura/manifest.json` 看真实皮肤定义了哪些键。
- **git 拆提交的最小粒度是文件**：两批改动纠缠在同一文件时，与其硬拆出一个测试挂掉的中间提交，不如按"能否独立通过测试"重新切分。（另见 §9.3。）

---

## 12. 不用干什么（明确排除）

（源：`HANDOVER.md` §六，2026-08-30；**逐条保留**）

1. 不要再改 `anima/core/`（v1.1.1 冻结）。
2. 不要重复做 Phase 4 聊天（已落地；流式打字机渲染留到后续优化）。
3. Phase 5 已完成（含打包/性能/tag v1.0），不要再重复做。
4. 不要删 `<本地归档目录>/core` 归档（等真机确认后）。
5. 不要重写编辑器（原样平移 + 数据源改造，别改布局；样式统一走 `anima/utils/theme.py` 的 QSS 工厂，勿再各写各的 QSS）。
6. 不要在编辑器里引入新依赖（PyQt6 + pydantic 已够）。
7. 不要动 YingPet-v4 源码（只读参考）。
8. **不要再尝试 PNG 256 色量化**（08-30 实测）：体积能再砍 80%，但 PSNR 只有 25.7~30.3dB，脸颊渐变肉眼可见色带。
9. **不要再尝试换 WebP**（08-30 实测）：q85 只有 PNG 的 18~22%，但换格式破坏用户自制 mod 生态，违反核心设计。
10. **不要再写 `QPixmap(path).scaled(...)`**：一律用 `load_scaled_pixmap()`。
11. 不要给主题测试写死色值断言：断言"回退到默认值"，否则换配色就要改测试。

---

## 13. 可继承的工作资产

（源：`HANDOVER.md` §七）

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
- `anima/window/dialogs/skinmaker.py` + `mods/feature.skinmaker/`：皮肤工坊（取色 + 实时预览生成 ui.* 皮肤）。
- `anima/window/dialogs/charcard/`：编辑器 GUI（dialog/wizard/assets；等待工具已上移 `dialogs/common`，包内再导出兼容）。
- 对话框平移先例：`settings.py` / `modmanager.py`（mm 服务 + `dialogs/common.wait_fire`）。

---

## 14. 环境与复跑

（源：`HANDOVER.md` §九 + `docs/PROJECT_STATUS.md` §7.3）

```bash
cd AnimaPet

# 注意: 必须用项目虚拟环境。系统 python(managed 3.13.12) 没装 pytest,
# 直接 `python -m pytest` 会报 No module named pytest。
.venv\Scripts\python -m pytest tests/ -q          # 263 passed（08-30 该文件里的复跑注释口径）
.venv\Scripts\python tools\check_kernel_rules.py  # 纯标准库 + 行数检查（归档时脚本已从仓库根移到 tools/）
.venv\Scripts\python tools\export_chara_schema.py # schema 幂等
.venv\Scripts\python tools\optimize_assets.py     # 默认只预览, --apply 才写盘
.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run
.venv\Scripts\python tools\migrate_yingpet.py export-chara card.ying --out E:\ying.chara.zip
.venv\Scripts\python tools\migrate_yingpet.py import-chara E:\mio.chara.zip --activate
.venv\Scripts\python main.py                      # 真机启动（无控制台用 run.bat）

# 重新打包(会先删 dist/AnimaPet; 想保留旧产物先 --distpath 到暂存目录)
.venv\Scripts\python tools\build_exe.py
```

> ⚠️ **`check_kernel_rules.py` 目前会失败（归档时实测）**：该脚本断言 `anima/core` 总行数
> `< 1000`，但内嵌内核升到 v1.3.1 后已是 **1197 行**（v1.1.1 时为 840 行）。
> 纯标准库那一半检查通过；失败的是行数断言，属于内核升级带来的**既存漂移**，不是本次归档引入的。
> 阈值要不要放宽需由内核侧决定，归档时未擅自改动。

结项报告另给的"快速验证命令"（2026-08-23 口径，多一条 `benchmark.py` 与 `run.bat`）：

```bash
cd AnimaPet
.venv\Scripts\python -m pytest tests/ -q
.venv\Scripts\python tools/benchmark.py
.venv\Scripts\python tools/build_exe.py
run.bat
```

> 常见坑（来源同 §11）：系统 python 没装 pytest；`jsonio` 写入受项目根白名单限制，测试临时目录要 monkeypatch `jsonio._BASE`。

---

## 15. 2026-08-28 追加轮之一：UI/可维护性重构

（源：`docs/PROJECT_STATUS.md` §9，结项报告附录，**原文逐条保留**）

> **触发原因**：结项后复查发现 UI 层三类问题 —— ① 四个对话框各自维护一份白色 QSS，与主界面深紫配色割裂；② `wait_fire`/PNG 导入等逻辑存在 2~3 份拷贝；③ 聊天历史逐条渲染、动画定时器空转等性能问题。
> **本轮只动表现层与重复实现，不改任何行为契约**（事件名/信号/存储格式/插件接口全部不变）。

### 15.1 改动清单

| 类别 | 改动 | 涉及文件 |
|---|---|---|
| 主题统一 | `theme.py` 升级为主题设计系统：颜色单点定义 + `menu_qss()/dialog_qss()/panel_qss()` 样式工厂；四个对话框从白底换统一暗色主题 | `utils/theme.py`、`settings.py`、`modmanager.py`、`charcard/dialog.py`、`charcard/wizard.py` |
| 去重 | 新建 `window/dialogs/common.py`：收拢 3 份 `wait_fire`/`wait_rescan` 与 2 份动画 PNG 导入；`charcard/__init__` 保留再导出兼容 | `dialogs/common.py`（新增）、`modmanager.py`、`charcard/*` |
| 对话框合并 | modmanager 两个"新建模组"对话框合并为 `_NewModDialogBase` 基类（id 校验/冲突检查共用） | `modmanager.py` |
| 聊天面板 | 工具栏重组（导出/导入收进"备份 ▾"菜单）；历史回放/搜索/会话浏览改批量渲染（一次文档重排）；空历史显示新手引导；消息 HTML 标记收进 ChatPanel，`plugins/chat.py` 只传数据；状态栏不再靠字符串切割拼装 | `window/chat_panel.py`、`plugins/chat.py` |
| 设置对话框 | 改两步向导式（① 对话模型 ② 角色人设），字段带悬停说明，温度改 0~2 滑条 | `settings.py` |
| 性能 | Animator 帧定时器按需启停（无可画帧不空转，表情/动画播放自动唤醒）；聊天面板 20+ 次 `setStyleSheet` 合并为 1 次 | `window/animator.py`、`chat_panel.py` |
| 清理 | PetWindow 菜单构建拆出 `_populate_menu` 并走主题工厂；tray `_quit` 等小清理 | `pet_window.py`、`tray.py` |

### 15.2 验证

- 全量测试 **254 passed**（唯一测试改动：设置对话框温度字段改滑条后，`test_settings_dialog_saves_config_and_char_prompt` 同步驱动 `sld_temp`）；
- `python -m compileall` 全量通过；
- 离屏实例化宠物窗口/聊天面板/设置/模组管理/角色卡管理器并截图检查，布局与配色正常（offscreen 平台缺 CJK 字体，截图文字显示为方块属环境限制）；
- 专项验证 `clicked(bool) → 零参信号 .emit` 与 `QMenu.addAction(text, slot)` 两条信号链安全。

### 15.3 规模与状态、兼容性

- 13 个文件修改 + 1 个新增（`anima/window/dialogs/common.py`），**+616/−535 行**；
- **改动停留在工作区，尚未提交**（这是 2026-08-28 当时的记录；两批改动最终在 **2026-08-30** 提交为 `377e878`）；真机冒烟（`docs/RELEASE_CHECKLIST.md`）在本轮之后仍待执行；
- 皮肤模组（ui.*）兼容性：`merge_theme` 键集合未变，旧皮肤直接可用。

---

## 16. 2026-08-28 追加轮之二：面向新手的功能轮

（源：`docs/PROJECT_STATUS.md` §10，同日第二轮，**原文逐条保留**）

> **目标**：不懂代码的用户也能完成四件以前要写 JSON/摆弄文件夹的事 —— 导入聊天记录、配行为规则、做皮肤、导 GIF 动画。测试 254 → **263 passed**（新增 9 个）。

### 16.1 新功能

| 功能 | 说明 | 落点 |
|---|---|---|
| 聊天记录导入增强 | 「备份▾ → 从 JSON 恢复」弹出三选：**合并(保留现有+按内容去重) / 覆盖现有 / 取消**；合并时会话号紧凑顺延不冲突 | `plugins/chat.py`（`HistoryStore.import_json` 加 mode 参数） |
| 行为规则可视化编辑 | 角色卡管理器·行为页签重做：触发事件改**中文下拉**（摸头/拖动/闲置/深夜/聊天回复等 9 种 + 自定义），动作改为**搭建器**（说话/表情/动画三选一，台词下拉提示 `@idle.this.<段>`，支持增删/上移/下移），保存前强制"至少一个动作"并给新手话术提示；规则列表显示人话（"#1 被摸头 → 2 个动作·冷却5s"）；高级用户保留「编辑选中规则 JSON…」出口 | `window/dialogs/charcard/dialog.py` |
| 皮肤工坊（新功能模组） | 右键菜单新入口：从默认/现有皮肤起步，19 个配色项分组取色，**实时预览**迷你聊天窗，保存生成 `mods/ui.<id>/`（与手写皮肤同构），可勾选"保存后立即换上" | `window/dialogs/skinmaker.py` + `mods/feature.skinmaker/`（manifest+plugin，仿 charcard 门面模式） |
| GIF 导入 | GIF 自动解帧为 PNG 序列：模组管理「新建▾ → 导入 GIF 动画到素材库」、角色卡管理器「动画页签 → 导入 GIF 到本卡」「素材库页签 → 导入 GIF 到素材库」；用 QImageReader 解码（Qt 自带 GIF 支持，**零新依赖**），帧延时折算 fps（1~30），单 GIF 上限 600 帧 | `window/dialogs/common.py`（extract_gif_frames/import_gif）+ `charcard/assets.py`（import_gif_to_card） |

### 16.2 测试

- 更新：`test_full_stack`（真实 mods 计数 27→28、features 8→9）、`test_charcard` 行为写回改驱动新表单；
- 新增 9 个：`test_gif_import`(4：解帧/坏文件/素材库模组/卡内导入)、`test_skinmaker`(3：保存并应用/冲突与非法 id 拒绝/现有皮肤起步)、`test_chat_plugin` 合并导入(1)、`test_charcard` 自定义事件+JSON 出口(1)；
- 离屏截图验证行为页与皮肤工坊布局正常。

### 16.3 兼容性说明

- `HistoryStore.import_json(path)` 旧调用（无 mode）等价 overwrite，行为不变；
- 手写 ui.* 皮肤、behavior 规则 JSON 格式完全不变（可视化编辑只是它们的生成器）；
- 真机冒烟清单仍待执行（§15.3 同）。

---

## 17. 2026-08-30 性能/体积优化轮

（源：`HANDOVER.md` §十一）

### 17.1 成果（全部实测）

| 维度 | 前 | 后 |
|---|---|---|
| `dist/AnimaPet` 总计 | 286MB | **155MB**（−45.8%） |
| ├ 素材 `mods/` | 187MB | 89MB |
| └ 依赖部分 | 99MB | 67MB |
| 单张 emote 加载峰值 | 16.52MB | **0.89MB**（−94.6%） |
| idle 动画常驻（50帧@240px） | 22.9MB | **11.0MB**（−52%） |
| 整机运行工作集 | — | 87.6MB |

### 17.2 做了什么

- **内存**：`QImageReader.setScaledSize()` 解码即缩放（干掉全分辨率位图峰值）；AnimMod 的永不释放 `_cache` 换成全局帧 LRU（64MB 软预算，按 `(目录, 尺寸)` 分组，淘汰最久未用）。预算是**软**的 —— Animator 持有帧列表引用，淘汰只影响"下次要不要重解码"，不会打断正在播的动画。`LoaderPlugin.scan()` 处清缓存（素材热重载后失效）。
- **磁盘**：236 张 PNG 降到最长边 512（最大显示 320px 的 1.6 倍，留 HiDPI 余量），只降采样 + 重编码；`build.spec` 剔除 `opengl32sw.dll`(19.7MB) / `Qt6Pdf.dll`(4.4MB) / `Qt6Network.dll`(1.7MB) / 96 个翻译文件保留 3 个 `zh_CN`（共 −32MB）。已复核 `anima/` 内零处 QtNetwork/OpenGL/Pdf/WebEngine 引用（网络走 `requests`）。
- **UI**：修了浅色「樱粉」皮肤弹出深色右键菜单的真 bug（皮肤只定义 14 个基础键，`menu_bg`/`bubble_bg` 一直回落硬编码深色）；补齐 hover/pressed/focus/checked/disabled 状态、4 级高度层级、圆角滚动条、tooltip。

### 17.3 批次 A 审查结论（2026-08-30 盘点时做的）

- **🔴 必修：无**（未发现崩溃或数据损坏路径）。
- **A/B 兼容性：干净** —— 全仓 AST 扫描确认批次 A 调用的 `merge_theme`/`menu_qss`/`dialog_qss`/`panel_qss`/`bubble_qss`/`chat_bubble_html` 在批次 B 重写后全部存在且签名未变；`load_scaled_pixmap` + 帧 LRU 与 Animator 按需启停定时器无冲突，且定时器不存在卡死路径（`_decode_frames` 有 `_fallback_disc` 兜底，永不返回空表）。

**🟡 该修（4 项）—— 已于 2026-08-30 全部修完，见 `48c67b0` 与 `8a56b04`**：

1. **✅ 已修** 行为规则编辑器静默丢字段（`charcard/dialog.py`，**真会丢数据**）
   - `_action_from_editor()` L820-829 只产出单键 dict，`_update_action_from_editor()` L848 整体替换 → 现有 6 条规则中 3 条带 `after_ms`（如 `{"emote":"angry","after_ms":200}`），一按「更新选中」就丢。
   - 条件键只读写 `when`（L673/L691），但 `rule_engine.py:194` 是 `for cond_key in ("when","if")` → 用 `if` 的规则条件会丢。
   - `on` 支持列表（`rule_engine.py:182-184`），但 L662 `str(r.get("on"))` 会把 `["a","b"]` 写成字符串字面量 `"['a','b']"` → 规则静默失效。
   - `_on_action_selected` L864/L868 `setCurrentIndex(max(0, idx))`：id 不在下拉时静默选中第 0 项，一按「更新选中」就换成别的动作；`state_set`/`state_inc`/`emit`（`actions.py:82-84`）等非三选动作会走空分支，同样被误替换。
2. **✅ 已修** 四个对话框不跟随皮肤：`dialogs/common.py` 的 `apply_dialog_style` 硬编码 `merge_theme({})`。08-30 让皮肤真正生效后，浅色皮肤下主窗口/气泡/聊天面板变浅，对话框仍深紫 —— 与主题系统"全局一致"的契约矛盾。现按 `mods.ui` 取当前皮肤（拿不到 host 时回落默认，行为不变）；已用真实樱粉皮肤离屏验证：底色 `#fff5f8`、文字 `#4a3038`，无残留默认色。
3. **✅ 已修** GIF 导入失败留孤儿目录：`import_gif` / `import_gif_to_card` / `import_anim_to_card` 先建目录再写内容，中途抛错不回滚；`loader.py:274-275` 对无 manifest 目录 `continue` 静默跳过 → 目录永久残留（卡内更糟，会显示成一套空动画）。现三处都包 try/except，失败即 `rmtree` 再抛出。顺带修了重名序号先自增导致 `_1` 永远用不上的问题。
4. **✅ 已修** 历史合并导入只比现有：`chat.py` 的去重集合只由现有记录建一次且不回写 → incoming **内部**重复不去重（同一份备份连合两次消息翻倍）。现边遍历边加入 `seen`。

**新增/修正的测试（共 5 例，均已在旧逻辑下验证过会失败）**：

| 测试 | 验证方式 |
|---|---|
| `test_behavior_editor_roundtrip_preserves_fields` | 还原旧逻辑后 `KeyError: 'after_ms'`、`"['pet.petted', 'pet.drag_started']"` |
| `test_import_gif_rolls_back_dir_on_failure` | 还原后 `assert ['anim.broken'] == []` |
| `test_import_gif_to_card_rolls_back_on_failure` | 同上（卡内目录） |
| `test_history_import_merge_dedups_within_incoming` | 还原后 `assert 4 == 2` |
| `test_dialog_style_follows_current_skin` | QSS 中不含默认前景色 |

另**修正了 2 例原有断言**：`test_gif_import` 把"重名跳到 `_2`"这个 bug 当成了期望值，现按正确行为断言 `_1`（并补一句 `_2` 确认连号）—— 这类"照着观察到的行为写断言"的测试最危险，会把 bug 固化成契约。

> **测试计数口径的原文矛盾**：`HANDOVER.md` §一 说 264 → 268 是"修 4 个 🟡 时补的（GIF 回滚 2 / 合并去重 1 / 对话框皮肤 1）"，而此处列了 5 例新增测试（多出行为规则往返保真那一条，对应 263 → 264）。两处说法并列为原文口径，未做统一。

**测试缺口（当时未补）**：`test_gif_import.py` 只用单帧 1×1 GIF，`1 <= fps <= 30` 几乎恒真 → 平均延时折算/600 帧上限/失败清理三个分支实际都没测到；`test_charcard.py` 行为规则用例**无往返保真断言**（正是 🟡1 溜过去的原因）；`test_skinmaker.py` 未测 id 路径安全、未断言 `_COLOR_FIELDS` 键均为合法 theme 键；`_NewModDialogBase` 两子类的 PREFIX/冲突检查无独立用例。

**🟢 建议（5 项）**：原文在 §11.3 末尾也列了一份，与 §17.4 高度重合；为避免重复，统一保留在 §17.4，两处措辞差异在该节标注。

### 17.4 🟢 建议项（未修，不急）

（源：`HANDOVER.md` §11.4。原文 §11.3 末尾与 §11.4 是两份高度重叠的 🟢 清单；此处按 §11.4 独立成节的那份表述保留，两处差异已在下文标注）

`assets.py` 残留未用 import `jsonio`/`paths`；`skinmaker.py:105,224` 两处 `setdefault("bubble_bg",...)` 是死代码（`merge_theme` 必有此键）；取色器 `col.name()` 会把 `rgba(...,230)` 转不透明 hex，头顶气泡失半透明；`common.py:114` GIF 截断只在日志告警、用户无感知；皮肤 id `a..`/`a.b..` 能通过校验（Windows 静默剥尾点 → 实际目录 `ui.a` 但 config 记 `ui.a..`，皮肤不生效；`../../evil`、`a/../b` 等穿越已正确挡住）；`animator.py::play_frames` 在 `back_to_idle` 不清空 → 播过一次后"按需启停"永久失效（不影响功能，只是省电退化）。

另有几处控件还在自己写死 QSS（如 `charcard/assets.py` 的 `PreviewBox` 硬编码 `#1d1526`/`#b04060`），与 §12.5「样式统一走 `theme.py` 工厂」相悖 —— 换皮肤时这些控件不会跟着变，建议一并收拢。

**测试缺口（未补）**：`test_gif_import.py` 只用单帧 1×1 GIF，`1 <= fps <= 30` 几乎恒真 → 平均延时折算与 600 帧上限两个分支仍没测到；`test_skinmaker.py` 未测 id 路径安全、未断言 `_COLOR_FIELDS` 键均为合法 theme 键；`_NewModDialogBase` 两子类的 PREFIX/冲突检查无独立用例。

> 另：原文 §11.3 末尾的同一项多了一句"且'恰好 600 帧'时可能误报"，§11.4 未提；两处同指一条建议。

---

## 18. 为什么没有继续推进（结项当时）

（源：`docs/PROJECT_STATUS.md` §6，2026-08-23 口径）

按原计划，发布前只剩：

- 真机冒烟（`docs/RELEASE_CHECKLIST.md` 已备好）；
- 确认后删除 `<本地归档目录>/core` 归档；
- 可选：exe 图标/单文件版/签名。

由于**项目被认为"没有实际使用价值"**，开发在此收尾。**代码与文档保留在仓库中，作为存档与未来参考**。

---

## 19. 未来若要复用/重启

（源：`docs/PROJECT_STATUS.md` §7）

1. 跑真机冒烟清单，修问题后即可作为个人工具使用；
2. 若想换方向，最有复用价值的是：
   - `.chara` 角色卡格式 + JSON Schema；
   - FeatureContext 插件契约与热重载模型；
   - 双线程（Qt + asyncio）桥接范式；
   - 按角色隔离的数据目录约定。
3. 快速验证命令见 §14。

---

## 20. 一句话总结

（源：`docs/PROJECT_STATUS.md` §8，2026-08-23）

> AnimaPet 完成了"从 YingPet 单机项目 → 插件化桌面宠物元框架"的迁移，代码质量与自动化测试完整，但作为产品缺少真实用户验证；当前以 v1.0 存档，源代码、格式规范、开发文档与打包产物均已就位。

---

## 21. 参考文档

（源：`HANDOVER.md` §十，并补记本文档之后的归属）

- 总计划：`PLAN.md`（Phase 0-4 ✅；Phase 5 待做 + 验收标准）—— 注：这是 08-30 当时该条目里的表述，实际 Phase 5 当时也已完成（见 §7）。
- `.chara` 格式规范：`docs/chara_format.md`；JSON Schema：`docs/schema/chara.schema.json`
- 两批未提交改动的详细记录：`docs/PROJECT_STATUS.md` §9（08-28 重构）、§10（08-28 功能轮）
- 运行期笔记：`.workbuddy/memory/MEMORY.md`（项目约定）+ `.workbuddy/memory/2026-08-30.md`
- 内核 API / 并发模型 / 插件模板：`Anima-v1.1\docs\` 三份
- 迁移源（只读）：YingPet `feature.charcard/*` + `tests/test_charcard.py`（改写蓝本）
- **本文档之后（现役）**：内核升级与版本记录 → `docs/kernel_upgrade.md`（即原根目录 `内核更换说明.md`，已改名归档到 `docs/`）

---

## 22. 附录 A：测试数量口径说明（253 / 254 / 263 / 268 / 346）

三份文档（以及三份文档之外被交叉引用的 `README.md`、内核更换说明）对测试总数**口径不一致**，原因是测试套件在各阶段持续增长，而各文档写在不同的时间点。**本文档不擅自取单一值**，全部口径并列如下：

| 数字 | 出处 | 时间 / 语境 |
|---|---|---|
| **253** | `README.md`（"当前 253 passed"） | 时间点不明。与结项日报的 254 差 1，原文未解释（推测是 README 未随结项回填，但**这是推测，文档没有说明**） |
| **254** | `docs/PROJECT_STATUS.md` §2、§9.2；`docs/RELEASE_CHECKLIST.md` | **2026-08-23 结项口径**；§9.2 明写"全量测试 254 passed" |
| **263** | `docs/PROJECT_STATUS.md` §10（"254 → 263，新增 9 个"）；`HANDOVER.md` §二、§四（目录地图）、§九（复跑注释） | **2026-08-28 功能轮之后** |
| **268** | `HANDOVER.md` §一（"测试 268 passed"、复跑输出）、§二提交索引（`377e878` 说明里写"tests 263 个用例"） | **2026-08-30 口径**：263 → 264 补行为规则往返保真测试；264 → 268 修 4 个 🟡 时补 4 条 |
| **346** | 内核更换说明（现 `docs/kernel_upgrade.md`）的 v1.3.1 补充说明 | **本文档之后**：内嵌内核升到 v1.3.1、`tests/test_core/` 与上游同步后的 AnimaPet 全量口径 |
| **104** | `PLAN.md` §一 | **不是全量测试数**，仅指 `work/` 仓库 Anima 内核 v1.0 的内核测试数量（104 个，覆盖率 99%） |

同一文档内部的矛盾（值得记住的教训）：

- `HANDOVER.md` **§一 说 268 passed，§四 目录地图说"tests 263 个"，§九 复跑注释也写 263** —— 三处同文不同数。
- `HANDOVER.md` §一 把 264 → 268 归因为"修 4 个 🟡 时补的（4 条）"，而 §十一 同一轮又写"新增/修正的测试（共 5 例）"。两处口径并列，原文未统一。
- 结论/教训：**测试总数是随时间漂移的量，引用时必须带日期口径**；文档里的复跑注释很容易忘记跟着更新。

同类的"带日期才成立"的数字（一律按当时口径引用，不代表当前值）：

| 数字 | 口径日期 | 出处 |
|---|---|---|
| 启动 1.520s / Python 峰值 6.5 MiB（offscreen） | 2026-08-23 | `PLAN.md` Phase 5、`PROJECT_STATUS.md` §2 |
| 整机运行工作集 87.6MB；`dist/AnimaPet` 155MB | 2026-08-30 | `HANDOVER.md` §一、§十一 |
| `check_kernel_rules.py` 840 行 + 纯标准库 | 2026-08-30 | `HANDOVER.md` §一、§九 |

---

## 23. 附录 B：本文档的取舍说明（压缩了什么、丢弃了什么）

便于对照与审计，此处显式列出合并时的取舍：

**压缩（内容保留、形态合并）**

- 三份文档中重复的"Phase 0-5 ✅ 完成 / tag v1.0"进度叙述 → §7 一张总表 + §7.3 技术要点。
- `PLAN.md` §五 各 Phase 的逐项 `[x]` 勾选清单 → 合并进 §7.2/§7.3（验收结论与实质技术信息保留）。
- 按会话叙述的"本会话完成的工作"（`HANDOVER.md` §一）与逐提交内容索引（§二）→ §9.2 的单条时间线 + 一行一提交索引表。
- `PROJECT_STATUS.md` §9.3 与 `HANDOVER.md` §一 中关于"两批改动尚未提交"的表述 → 统一说明为"当时未提交，2026-08-30 以 `377e878`/`caae6b0` 落地"。

**丢弃（判定为已被取代或纯事务性，不含可继承的决策/经验）**

- `PLAN.md` §八"立即行动（本周）"—— 立项当周的四条待办（内核升 v1.1、建仓、Phase 1 开工、建功能对等清单初稿），均已完成或已由 §7 覆盖。
- `HANDOVER.md` §二 中"提交与未提交状态"里关于"工作区是否干净"的即时状态描述（随时间失效）。
- `PROJECT_STATUS.md` §4 提交链里省略号处的逐提交清单（其可考的提交已并入 §9.2）。
- 各文档抬头里的重复元信息（项目定位、位置、上游路径等重复出现的部分合并到 §1 与 §14 一次说明）。
- 指向"本文档之后"内容的详细记录（内核 v1.3.x 的升级细节）—— 按要求只在此处指向 `docs/kernel_upgrade.md`，不复制其内容。

**未处理的歧义（如实保留）**

- 测试总数（附录 A）与 264 → 268 的归因（§17.3 引用块）。
- `HANDOVER.md` §十 说 `PLAN.md` "Phase 5 待做"，而同文档 §一 说 Phase 0-5 早已完成 —— §21 已加注说明。
- `README.md` 的 253 与结项 254 的差额，原文无解释。

---

## 24. 2026-09-22 归档整理、渲染优化与后续修复（托盘 / API 排查）

本节由归档整理时补写，记录 §1–§23 之后发生的事，避免本文档立刻重新过期。

### 24.1 文档归档（本次）

- 本文档由 `PLAN.md` + `HANDOVER.md` + `docs/PROJECT_STATUS.md` 三份合并而成，三份源文档已删除
  （git 历史可取回）。
- `内核更换说明.md` → `docs/kernel_upgrade.md`；`check_kernel_rules.py` → `tools/check_kernel_rules.py`
  （脚本内 `__file__` 路径已同步改为 `parents[1]`）。
- `dist/` 与 `build/` 作为可再生产物清理（约 414.6 MB），需要时用 `tools/build_exe.py` 重建。
- `tools/check_kernel_rules.py` 与上游不一致的根因已解决：本仓那份还是 v1.1 的**单条 `raw < 1000`**，
  而内核升到 v1.3.1 后是 1197 行 —— 上游 v1.2 起早已拆成 `raw < 1200` + `code < 650` 两条。
  现已按上游口径同步（实测 `raw=1197 / code=622` 通过，import 检查通过）。
  ⚠️ `raw` 只有 3 行余量（1197/1200），再加 docstring 就会顶到上限。

### 24.2 动画渲染优化（本次，含实测）

用 `tools/bench_anim.py`（本次新增，offscreen）量化后定位到两类问题：

| 测量项 | 优化前 | 结论 |
|---|---|---|
| `advance()` 选帧逻辑 | 0.0024 ms/帧（定时器 80–120ms） | 占空比可忽略，**不是瓶颈** |
| 气泡 `_tick` | 0.045 ms/字符 | Python 侧可忽略 |
| 静态表情 / 单帧动画的 `setPixmap` | 100 次 tick 里 **99 次画的是同一张对象** | **真浪费：已修** |
| 冷解码（40 帧 idle + 40 帧 talk @240px） | **96 ms，同步阻塞 Qt 主线程** | **真卡顿：已修** |
| 换角色卡/换尺寸（清缓存后 `refresh_from_registry`） | 240px **85 ms** / 320px **100 ms**（同尺寸热切换 0.1 ms） | 同上，**已修** |

**修复一：重复重绘。** `Animator._paint()` 按 QPixmap 对象同一性跳过重复 `setPixmap`。
`QLabel.setPixmap` 无条件触发 `update()`，而宠物窗口是 `WA_TranslucentBackground` 的无边框窗口，
每次 update 都让整个半透明窗口重新合成。修复后这两类内容的重绘从 **100 次降到 1 次**（画面完全不变）。
回归测试：`tests/test_plugins/test_window.py::test_animator_skips_redundant_repaint`。
另外 `bubble._tick()` 原先自己做一遍 `adjustSize()+resize()` 后 `_reposition()` 又做一遍，
每个字两趟 QLabel 重排，已去重。

**修复二：冷解码冻结（异步解码）。** 分工改为：

1. **主线程**只同步解**第一帧**（约 1–2 ms）立刻出画，然后 `prefetch()` 走人；
2. **工作线程**解其余整组 —— 只产出 `QImage`（可跨线程），不碰 `QPixmap`/`QWidget`；
3. 解完经 **queued signal** 回 Qt 主线程，转 `QPixmap` 写进 `_frame_lru`，再回调窗口重装整组。

跨线程手法与 `anima/plugins/bridge.py` 的 `_UiBridge` 完全一致（信号 + 排队投递）：
跨线程只传数据，GUI 对象一律在 Qt 主线程构造。因此 `_frame_lru` 只被主线程读写，无需加锁。

**实测结果（`tools/bench_anim.py`）**：

| 冷切换 | 优化前 | 优化后 |
|---|---|---|
| 240px | 85.3 ms | **2.9 ms**（先出画 1 帧 → 后台补齐 40 帧） |
| 320px | 100.3 ms | **4.9 ms**（先出画 1 帧 → 后台补齐 40 帧） |

契约保持不变：`AnimMod.frames()` 仍是同步、完整返回（命中缓存直接给整组，未命中同步兜底解码），
所以 `len(anim.frames(size)) == 50` 这类断言与 registry 对外语义都没变；
`instant_frames()` 只用在窗口装配路径上，且**刻意不把"只有一帧"的结果写进缓存**，
否则 `frames()` 会把单帧当成整组返回。

**踩到的坑（值得记住）**：投递器 `_FrameReady` 起初做成模块级复用，整包测试里炸了 ——
`QObject` 的 C++ 实体随 `QApplication` 存亡，而各测试模块各自创建 `QApplication`，
复用必然拿到已删除的包装器（`wrapped C/C++ object of type _FrameReady has been deleted`）。
改为**每次 prefetch 现建一个、登记进 `_live_marshallers` 保活到槽执行完**（投递是异步的，
提前放手会被 GC）。单跑该模块是绿的，只有整包跑才暴露。
回归测试：`tests/test_plugins/test_window.py::test_prefetch_fills_frame_group`。

**踩到的第二个坑（更严重，会崩进程）**：后台线程在用 Qt 的图像 API（`QImageReader`），
若它跨过 `QApplication` 析构的时点，会直接 `access violation` 崩掉进程 —— 整包测试退出时
实测崩过（崩点 `anima/mods/loader.py:163 in _decode_to_images`）。原先的 `shutdown_prefetch()`
只丢弃回调，**并没有让在途线程停手**，所以真机退出时同样会崩。修法三件套：

1. `_decode_to_images()` 逐帧检查退出标志，置位即收手；
2. 在途线程登记进 `_workers`，`shutdown_prefetch()` 置标志后 `join` 等它们结束；
3. 测试侧 `tests/conftest.py` 加 autouse fixture，每例结束 `drain_prefetch()`
   （只等、不置标志，所以后续用例的预解码照常可用）。

**教训**：跨线程只传"数据"还不够 —— 还要保证线程不会**跨过 Qt 的生命周期边界**。
`daemon=True` 只保证进程能退出，不保证线程不在错误时点碰 Qt。

**被否决的备选**（记录理由）：逐帧惰性解码 —— 首轮播放按需解码，把 96 ms 摊到 40 × 80 ms，
无新线程；但 `AnimMod.frames()` 要从"立即返回 list"改成惰性序列，会动 registry 对外契约与多处断言，
收益也不如异步方案（异步是 85 ms → 3 ms，且首帧即出画）。

### 24.3 顺带发现（未改）

- `AnimMod.fps`（manifest 的 `fps` 字段）被解析但**从未被 Animator 使用**：定时器间隔是
  写死的 80/90/120 ms。独立 `type=anim` 模组声明的帧率目前是失效的。

### 24.4 修复：系统托盘一直没生效（排查 API 问题时在日志里发现）

`data/pet.log` 里一直有这条，但因为是 WARNING 且被吞掉，没人注意：

```
[WARNING] main tray init failed: name 'registry' is not defined
```

原因：`main._run()` 里写的是 `TrayController(registry, cfg, bridge)`，但这三个名字都是
`_build_stack()` 的**局部变量**，`_run()` 作用域里并不存在 → `NameError` → 被 `except`
吞成一条 warning。**所以 Phase 5 的托盘功能从来没有生效过**，而 README 与
`RELEASE_CHECKLIST.md` 里"托盘可切换角色/皮肤/退出"的说法此前并不成立。

修法：新增 `main._setup_tray(core, bridge)`，用内核已 provide 的服务构造
（`core.registry.use("mods")` / `use("config")`，分别由 `LoaderPlugin` / `ConfigPlugin` 提供）。
另外**必须持有返回值**：`TrayController` 是无父 `QObject`，原写法连引用都没留，
即便修掉 NameError，对象也会被 GC、托盘图标随即消失。现在赋值给 `tray` 并活到
`app.exec()` 结束，日志里也会写明 `tray=on|off`，不再静默。

回归测试：`tests/integration/test_full_stack.py::test_tray_binds_to_kernel_services`。
（这类 bug 能长期潜伏，根因就是零覆盖 + 异常被吞；`except` 里只记 warning 的地方，
测试很难发现，值得对"静默降级"的路径保持警惕。）

### 24.5 排查 API 时的环境事实（未改动代码）

用户报"接入 API 后无法使用"，定位为**配置填法**问题，非代码缺陷：

- `base_url` 填成了完整端点且尾部多一个反斜杠：
  `https://openrouter.ai/api/v1/chat/completions\`。适配器契约是
  `base.strip().rstrip("/") + "/chat/completions"`（`anima/adapters/openai_compat.py:37-44`），
  于是实际请求 `…/chat/completions\/chat/completions`。
  实测该地址返回 **404**，正确 base（`https://openrouter.ai/api/v1`）返回 **401**（通，仅缺 key），
  与日志 `API 404` 吻合。设置界面本就把该字段描述为"接口地址（默认 https://api.deepseek.com）"。
- 另有两类与配置无关的现象：免费模型 `qwen/qwen3.8-27b:free` 被上游 **429 限流**
  （该模型 id 真实存在）；以及一次 `ConnectionResetError(10054)` 偶发断连。
- `data/config.json` 明文存 api_key（原设计如此，`data/` 已 gitignore）。
