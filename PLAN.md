# AnimaPet 迁移开发计划

> **项目**: AnimaPet —— 基于 Anima 内核的桌面宠物元框架
> **性质**: 将 `E:\dsh-work\YingPet-v4`（6,681 行 Python）迁移到 Anima 插件内核（已冻结 v1.0）
> **落地位置**: `E:\Zcode-work\AnimaPet`
> **依据**: 《Anima 桌面宠物元框架开发规划书》（本目录 .txt）+ YingPet-v4 实测架构盘点
> **日期**: 2026-08-18

---

## 一、现状盘点（三份资产）

### 1. Anima 内核（`E:\Zcode-work\work`，已完成 ✅）

规划书 Phase 0 的交付物已经存在：735 行纯标准库内核，104 个测试全绿，
总覆盖率 99%（各模块 ≥97%），含 App/EventBus/ServiceRegistry/
LifecycleManager/Context/EffectTracker/Plugin/异常体系，Kahn 拓扑排序、
LIFO 副作用回滚、通配符订阅（`"*"` 可当 on_all 用）、同步/异步插件方法
统一调度。接口已按冻结流程文档化（docs/architecture.md、core_api.md、
maintenance.md）。

### 2. YingPet-v4（迁移源，架构上"半成品同路人"）

v4 已经完成了"核心冻结、功能全模组化"的重构，与规划书的目标架构高度同构：

| 层 | 现状 | LOC | 与目标的差距 |
|---|---|---|---|
| core/ | 自制迷你内核：EventBus/Registry/ActionRegistry/RuleEngine+safe_eval/FeatureContext/Harness/热重载 | 2,182 | 不是 Anima 内核；UI（window/animator/bubble/theme）混在 core 里 |
| mods/ | card.ying 角色卡 + 9 个功能插件（chat/settings/charcard/weather/todo/packer/sysmon/clock/hello）+ 3 套皮肤 + 全局行为 | 3,458 | 插件契约是 `FeatureContext` 白名单而非 `Plugin` ABC |
| tests/ | offscreen 模式 Qt 测试 6 个文件 | 859 | 需改写到新内核 API |
| 并发模型 | **纯同步 Qt**（QTimer/QThread），全工程无 asyncio | - | 与 async-first 的 Anima 内核需要对桥 |
| 依赖 | requirements.txt 只有 `PyQt6>=6.6`；**requests 实际被用但未声明** | - | 需补齐 |

### 3. AnimaPet 目录（`E:\Zcode-work\AnimaPet`）

目前仅有规划书 .txt。本计划为第一个项目文件。

**结论**: 迁移 = ①把 YingPet 的 core/ 拆解为"Anima 内核（外购）+ 官方插件
+ 渲染层"，②把 mods/ 的 FeatureContext 插件改写为 `anima.core.Plugin`
契约，③数据格式平滑迁移。大量代码是**搬运改写**而非重写。

---

## 二、目标目录结构（AnimaPet）

```
E:\Zcode-work\AnimaPet\
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

---

## 三、关键技术决策（TD）

### TD1 事件循环整合（最大风险点，已定方案）

YingPet 是纯同步 Qt；Anima 内核是 async-first。**推荐方案 A**：

**A（推荐）：内核 asyncio 循环跑在后台守护线程，Qt 占主线程**
- `main.py`：Qt 主线程照常 `app.exec()`；内核循环
  `asyncio.new_event_loop()` 在 daemon 线程启动，
  `run_coroutine_threadsafe(app.start(plugins), loop)` 驱动生命周期。
- UI 线程规则（写入 plugin_dev_guide，强制）：
  1. `PetWindow`/对话框等 QWidget **只能在 Qt 主线程创建与访问**——由
     bridge 插件在 Qt 线程（main.py 里先建窗口再 start）持有；
  2. 后台线程/协程要更新 UI，一律 `bridge.run_on_ui(fn)`（内部
     `QMetaObject.invokeMethod` 队列）或发总线事件由 Qt 线程订阅者处理；
  3. 同步 `bus.emit` 从任意线程调用是安全的（内核数据结构无 await 临界区），
     规划书的事件流（click → rule → action → bridge → UI）全走同步 emit，
     天然落在 Qt 线程。
- 优点：零新增依赖、qasync 的边界问题全部避开、线程归属清晰。
- 代价：插件作者需理解两条线程规则（用 bridge API 封装后基本无感）。

**B（备选）**：qasync 统一循环。规划书风险表提到的原方案，模型更简单
（单线程、可 await），但引入新依赖且与 PyQt6 版本偶有兼容问题。若 A 在
集成测试暴露难以解决的时序问题，切换到 B 的改动集中在 bridge 与 main.py。

### TD2 内核小版本升级 v1.0 → v1.1（走冻结变更流程）

迁移暴露的内核缺口，按 maintenance.md 的流程补齐（均为**新增**，非破坏性）：

| 缺口 | 来源 | 方案 |
|---|---|---|
| `ctx.task(coro)` | 规划书 §2.2.2：任务卸载自动 cancel | `Context.task()` + `EffectTracker.push_task()`：注册即记录 cancel 回滚 |
| `bus.on_all` | RuleEngine 需要监听一切事件 | **不需要改**——`subscribe("*")` 已覆盖 |
| 类型形式 provide/use | 规划书 §6.3 `ctx.use(ConfigService)` | 插件层薄封装：类 → `f"{cls.__module__}.{cls.__qualname__}"` 字符串键，内核不动 |
| 线程安全 emit | TD1 的 Qt 线程调用 | 语义已满足；在 bus docstring 明确"单写多读、无 await 临界区"结论 |

升级在 `work/` 仓库完成（附测试、更新三份文档、`__version__ = "1.1"`），
再同步复制到 AnimaPet；work/ 保留为内核上游。

### TD3 Pydantic 只做边界校验

`models/` 用 Pydantic v2 校验 manifest/config/角色卡/聊天记录的**加载边界**
（坏文件 → 明确错误 + 降级默认值，沿用 YingPet"绝不因坏数据崩溃"的原则）。
内核与插件内部传参不引入 Pydantic 类型，避免渗透。

### TD4 角色卡格式：YingPet card.* 规范化为 .chara

YingPet 的 `card.ying/` 结构（manifest + emotes.json + idle.json +
behaviors.json + anims/frames + images）经过实测，规划书的 `.chara`
manifest（附录 A）是它的超集视图。**采用 YingPet 物理结构 + 规划书
manifest 字段**做统一格式，Pydantic 模型双名字段兼容（如
`expressions` ↔ `emotes.json`），`tools/migrate_yingpet.py` 做一次性转换
与校验。帧动画沿用 PNG 序列（不引入 GIF/WebP 渲染路径，规划书 §3.3 的
扩展留到 Phase 5+）。

### TD5 LLM 适配器接口

YingPet 只有 OpenAI 兼容单适配器（DeepSeek 默认）。抽
`LLMProvider` 抽象（`async chat(messages, config) -> Reply(emotion, text)`），
首个实现 `openai_compat` 100% 复用现有请求/解析逻辑（含 emotion 白名单
校验、降级策略）。`requests` 显式进 requirements；QThread 改为
`asyncio.to_thread` 包同步调用（留在内核线程池，不碰 UI 线程）。

### TD6 工程与运行时约定

- 依赖：`PyQt6>=6.6`、`pydantic>=2`、`requests`；dev：`pytest /
  pytest-asyncio / pytest-cov`。AnimaPet 建独立 `.venv`。
- 保留 YingPet 的工程韧性：单实例 Win32 互斥锁、`pythonw` + 原生
  MessageBox 的致命错误通道、`sys.excepthook` 不退出的最后防线、
  `QT_QPA_PLATFORM=offscreen` 测试模式。
- 事件命名沿用规划书 §6.2（`域.对象.动作`），YingPet 事件名
  （`user.click`、`chat.reply`、`timer.sit` 等）已在迁移映射表中逐一对齐。
- Git：AnimaPet 新仓库，按里程碑提交（沿用 work/ 的 conventional commits）。

---

## 四、迁移映射表（核心干货：YingPet → AnimaPet）

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
| mods/feature.{weather,todo,sysmon,clock,hello,packer} | ~834 | mods/ 同名（用户模组层） | FeatureContext API → Plugin+Context API：`ctx.emit/on`同名保留；`ctx.say/emote` → `use("bridge").say/emote`；`ctx.get/set_state` → `use("state")`；`ctx.add_menu_action` → `use("module_manager").add_menu`；QThread 采样器保留 |
| mods/card.ying、behavior.health、ui.* | ~560 | mods/ 原样 + tools 转换 | 行为/皮肤 JSON 兼容；card 增补 manifest 新字段（工具自动） |
| tests/* | 859 | tests/test_plugins/ + integration/ | 断言从 Harness/FeatureContext 改为内核 API；offscreen 模式保留 |
| main.py | 81 | main.py | 保留单实例锁/异常通道；启动序改为：Qt → 内核线程 → App.start(官方插件) → PetWindow → bind |
| tools/migrate_v3_to_card.py | 101 | 删除 | 历史工具，v4 已消费 |

**改写量估算**: 原样/近原样搬运 ~2,600 行（utils/window/animator/bubble/
safe_eval/皮肤与数据模组/功能模组小改）；需实质改写 ~1,700 行（harness
拆解、loader/rule_engine 契约化、chat 拆分、settings/charcard 对接）；
新写 ~800 行（bridge、11 个插件壳与编排、tray、adapters、迁移工具、
main.py 新启动序）。

---

## 五、分阶段计划

> 规划书 12 周路线图的 Phase 0 已由 work/ 内核完成；YingPet 代码可复用度高，
> 整体压缩到 **6 个阶段 / 约 6-7 周等效工作量**。每阶段以"验收可运行"收口。

### Phase 0：内核安置与升级（0.5 周）✅ 完成

- [x] Anima 内核 v1.0（work/ 仓库，104 测试，覆盖率 99%）
- [x] work/ 内核升级 v1.1：`ctx.task()` + push_task（含测试与文档更新）
- [x] AnimaPet 仓库初始化：目录骨架、pyproject、venv、内核与 test_core 复制
- [x] 冒烟：`asyncio.run(App().start([]))` 通过；pytest 全绿

**验收**: `pytest tests/ -v` 全绿；`check_kernel_rules.py` 通过。

### Phase 1：最小可运行宠物（1 周）—— 规划书 Phase 1 ✅ 完成

任务（按依赖序）：
1. [x] `anima/utils/`（jsonio/paths/log/theme 原样）+ `anima/events.py` 常量表
2. [x] **config 插件**：DEFAULT_CONFIG、点路径 get、原子保存、`provide("config")`
3. [x] **state 插件**：change 漏斗 + 持久化 + `state.changed` 广播
4. [x] **actions 插件**：注册中心 + state_inc/state_set/emit
5. [x] **window 层搬运**：pet_window/animator/bubble（去 harness 引用）
6. [x] **bridge 插件**（本阶段最难，TD1 落地）：Qt 主线程持有 PetWindow；
   `run_on_ui` 封装；注册 say/emote/anim 动作；功能菜单登记
7. [x] **loader 插件**（先支持 card + ui + behavior 只读扫描，功能模组下一阶段）
8. [x] **main.py**：单实例锁 → Qt → 内核线程 → start → card.ying 显示
9. [x] 集成测试：offscreen 模式启动 → 角色显示 → emit user.click → 冒泡

**验收**: `python main.py` 启动，ying 角色待机动画正常，点击/拖拽/
双击事件到总线，右键菜单可 emote、可退出；行为规则（petted 加好感）触发。
（offscreen 冒烟实测通过：20 模组对象 0 错误、规则 7 事件订阅、角色帧加载；
真机 GUI 交互待用户环境双击验收。）

### Phase 2：业务全插件化（1.5 周）—— 规划书 Phase 2 ✅ 完成

1. [x] **hotreload 插件**：QFileSystemWatcher + 800ms 防抖 → 经
   module_manager.rescan（线程感知调度到内核循环，注册表重建无竞态）；
   watcher 是 QObject，经 bridge.run_on_ui 保证在 Qt 主线程创建；
   `_feature_data` 等价物 = `module_manager.feature_data(id)`（热重载状态不丢）
2. [x] **rule_engine 插件** + safe_eval 原样搬运 + 规则/动作/模板全量回归
   （内核通配订阅 `"*"` 的 handler 收不到事件名，改为按规则声明的
   事件名逐个订阅，语义与 on_all+过滤等价，订阅随 mods.reloaded 重建；
   后续优化：事件分发索引 + 每事件一次快照）
3. [x] **character_manager 插件**：card 生命周期、active 切换、归属过滤、
   `character.switch`→窗口刷新→`character.switched` 事件链（功能模组可经
   `use("character_manager").switch(id)` 程序化切换）
4. [x] **module_manager 插件**：启用/禁用（持久化到 config.mods.enabled）、
   菜单注册服务、ModsDialog/SettingsDialog 对接 lifecycle（feature 适配器
   强制 `dependencies=[]`，禁用=完整卸载、再启用=全新实例重新 on_load）
5. [x] 六个功能模组改写（weather/todo/sysmon/clock/hello/packer）：
   FeatureContext 白名单契约与 YingPet 同名平移（仅 import 改 anima；
   packer 纯函数复用 anima.mods.packer）；设置对话框并入 module_manager
   （API / 人设写回角色卡 manifest）
6. [x] `tools/migrate_yingpet.py`：config/state/chat_history 平移 + 字段补齐
   （默认结构合并、未知键留 _legacy、功能模组状态随 state 平移、写前备份
   data/backup/、源目录只读、--dry-run）
7. [x] 测试改写 + 热重载专项：YingPet test_harness（对等回归并入集成测试）、
   test_safe_eval、test_plugins_v31（→test_features.py）、test_ui_mod 已改写；
   **test_charcard 已随 Phase 3 角色卡编辑器落地改写；test_chat_plugin 随
   聊天(Phase 4)时改写**；hotreload 专项（watcher 防抖/路径/插件接线/重扫生效/
   Qt 线程跨线程 rescan）已齐

**验收**: 与 YingPet-v4 功能对等清单逐项打勾（角色/行为/天气/待办/时钟/
系统监控/打包导入导出/设置 ✅；角色卡编辑→Phase 3 charcard 编辑器、聊天→Phase 4）；
拖入新模组 ≤1 秒热生效（800ms 防抖 + 同步重扫，专项测试覆盖确定性路径）；
卸载模组后 bus/registry 无残留（内核可逆性兑现，集成测试断言 bus.count()==0）。

### Phase 3：.chara 角色卡规范化（1 周）—— 规划书 Phase 3 ✅ 完成

1. [x] Pydantic 模型：CharacterCard/Expression/Animation/Behavior + JSON
   Schema 导出（docs/schema/chara.schema.json；tools/export_chara_schema.py
   生成，测试断言无漂移）
2. [x] 格式规范文档 + 迁移工具升级：docs/chara_format.md + migrate
   export-chara/import-chara（card.* ↔ .chara 互转）
3. [x] character_manager 对接新模型（card_model/history_dir）；charcard
   编辑器 6 页签 GUI 平移到 anima/window/dialogs/charcard/（dialog/wizard/
   assets），保存统一过 anima.models.load_card 整体预检，菜单接入
   module_manager「角色卡管理器…」
4. [x] 多角色并存与切换上下文隔离：聊天历史按角色分目录
   data/characters/<id>/chat_history.json（迁移工具按当前角色分流）
5. [x] ZIP 形式 .chara 加载：packer 扩展 + id/类型归一（chara→card、
   补 card. 前缀），Zip-Slip 防护复用

**验收**: 拖入 .chara 文件夹或 zip 安装新角色无需重启（offscreen 测试覆盖
安装+重扫可见）；坏 manifest 报错明确且应用不崩（整体校验/逐文件降级两套
测试齐全）；角色切换后人设/行为/历史完全隔离（数据层测试 + 编辑器写回测试）。
真机拖装/切换隔离仍在第 5 步用户环境冒烟。

### Phase 4：聊天与多 LLM（1 周）—— 规划书 Phase 4 ✅ 完成（代码+测试；真机 LLM 联调待用户环境）

1. [x] `LLMProvider` 抽象 + `openai_compat` 实现（`anima/adapters/` async 抽象 + openai_compat，sync requests 包 to_thread，解析/降级复用）
2. [x] chat 插件：`anima/plugins/chat.py` + `window/chat_panel.py`，面板信号对接、
   system prompt 注入人设 + emotion 白名单、`stream: bool` 配置已预留在
   DEFAULT_CONFIG（流式打字机渲染后续实现）
3. [x] 历史分角色/分会话存储（`data/characters/<id>/chat_history.json`）、搜索、
   单条删除（`HistoryStore.delete_message/delete_conversation`）、JSON 导入导出
4. [x] API key 仍存本地 config（沿用 `config.json api.api_key`；适配器缺 key/坏 key 降级为角色内错误回复）

**验收**: DeepSeek/OpenAI 任意 base_url 配置即用（适配器单测覆盖缺 key 降级）；
对话中角色表情随 emotion 字段切换（CHAT_REPLY 事件转发 emotion，行为规则已订阅）；
聊天记录可按 txt/JSON 导出导入；断网/坏 key 得到角色内错误回复。

### Phase 5：生态与收尾（1 周）—— 规划书 Phase 5 ✅ 完成

1. [x] **tray**（新增）：`anima/window/tray.py` + main.py 接入（角色/皮肤/退出）
2. [x] `docs/plugin_dev_guide.md`：Hello World、Context API、两条线程规则、
   打包规范 + `tools/new_plugin.py` 脚手架脚本
3. [x] PyInstaller 打包：`build.spec` + `tools/build_exe.py`，已成功构建 `dist/AnimaPet/`，offscreen 冒烟存活 8s
4. [x] 性能回归：`tools/benchmark.py` 实测启动 1.520s / Python 峰值 6.5 MiB（offscreen）；真机内存对比待用户
5. [x] README.md + 功能对等/进度说明；[x] tag v1.0（本会话收尾打）

**验收**: 第三方开发者按指南可写出并热加载插件（docs/new_plugin 已覆盖）；
打包 exe 已构建并 offscreen 冒烟；启动 1.520s 达标(<3s)；内存真机对比待用户。

---

## 六、风险与对策

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

## 七、里程碑总览

| 阶段 | 交付物 | 预估 | 出口标准 |
|---|---|---|---|
| P0 | 内核 v1.1 + 仓库骨架 | 0.5 周 | 测试全绿 + 铁律检查通过 |
| P1 | 最小可运行宠物 | 1 周 | main.py 启动，角色显示与基础交互 |
| P2 | 全功能对等 | 1.5 周 | 对等清单 100%，热重载可用 |
| P3 | .chara 规范 | 1 周 | 拖装角色、编辑器、多角色隔离 |
| P4 | 多 LLM 聊天 | 1 周 | 适配器可切换、历史可导出 |
| P5 | 生态与分发 | 1 周 | 打包 exe + 开发者指南 + v1.0 tag |

合计 **6 周等效**（对照规划书原 12 周：内核已完成 + 代码可搬运，压缩一半）。

---

## 八、立即行动（本周）

1. work/ 内核升级 v1.1（`ctx.task()`，含测试与三份文档同步）
2. AnimaPet 建仓：骨架 + venv（PyQt6/pydantic/requests/pytest 系）+
   内核与 test_core 复制 + 冒烟
3. Phase 1 开工：utils/events 搬运 → config/state/actions 插件（测试先行）
4. 建"功能对等清单"初稿（从 YingPet 使用说明书抽条目）

> 本计划批准后从第 1 条开始执行；每阶段结束提交 milestone commit 并
> 回填本文件的勾选状态。
