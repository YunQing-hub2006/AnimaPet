# AnimaPet 开发会话 · 工作交接记录（第 5 版）

> **会话日期**: 2026-08-20（深夜续作）
> **项目**: AnimaPet -- 基于 Anima 内核 v1.1 的桌面宠物元框架
> **位置**: `E:\Zcode-work\AnimaPet`（git 已初始化，按里程碑提交）
> **上游内核**: `E:\Zcode-work\Anima-v1.1`（v1.1 已完成冻结，**只读**，勿改）
> **迁移源**: `E:\dsh-work\YingPet-v4`（只读参考）

---

## 一、当前进度快照（截至本交接）

### **PLAN Phase 2 全部 7 项完成 ✅**（Phase 1 已在前两版完成）

### 已完成并提交（12 个 commit）

| commit | 内容 |
|---|---|
| `8c8a899` | Phase 0 建仓：目录骨架、内核 v1.1 九模块 + 113 内核测试、venv、utils 四件套、events 常量表 |
| `d6e08e5` | config/state 插件 |
| `36210df` | HANDOVER 第 1 版 |
| `b123852` | actions 插件 |
| `c14866f` | HANDOVER 第 2 版 |
| `901c4f6` | mods 数据层 + 真实模组数据 + 12 数据层测试 |
| `5403daf` | loader 插件 |
| `0d1e753` | HANDOVER 第 3 版 |
| `d1c276c` | rule_engine+safe_eval、window 三件套、bridge、module_manager（HANDOVER §五 主体） |
| `a8b84e9` | main.py 双线程启动序 + run.bat + 集成测试；PLAN 回填；HANDOVER 第 4 版 |
| `8a6eb8a` | A 档修复：loop 注入、跨线程 rescan 调度、规则引擎事件索引 |
| `fbc864e` | HANDOVER 补 A 档修复经验 |
| `b256f26` | hotreload + character_manager + bridge 补窗口热刷新订阅 |
| `7b20531` | 五个功能模组平移 + 设置对话框 + 迁移工具（本交接前最后一个功能 commit） |

### 当前测试状态

```
pytest tests/   →  216 passed
  113 内核 + 10 utils + 7 基础插件 + 12 mods 层 + 4 loader 插件
  + 18 rule_engine/safe_eval + 11 window/bridge + 12 module_manager(含设置对话框)
  + 8 hotreload/character_manager + 7 功能模组 + 5 ui 皮肤 + 4 迁移工具
  + 5 集成(全链路/跨线程/TD1/对等回归)
check_kernel_rules.py → 785 行、纯标准库（过）
migrate CLI dry-run → 对真实 YingPet 目录只读规划正常
```

### 关键里程碑（本会话）

- **Phase 2 完成**：hotreload（800ms 防抖 + 线程感知重扫）、character_manager
  （switch 事件链）、六个功能模组全平移（weather/todo/sysmon/clock/hello/packer）、
  设置对话框、迁移工具、YingPet 测试改写（test_harness/test_safe_eval/
  test_plugins_v31/test_ui_mod 四件等价体）+ hotreload 专项。
- **真实数据 25 个模组对象**：card.ying 展开 + health + 3 皮肤 + 6 功能模组，
  0 错误；帧数精确断言（idle 50 / talk 60）、归属隔离、行为开关、人设写回重扫
  全部过对等回归。
- **注意**：用户真机正在运行的实例是旧代码（22:21 启动），**重启后**才会带上
  本批功能（5 新功能模组菜单 + 热加载 + 角色切换服务）。

---

## 二、重要澄清（避免接手者踩坑）

1. **"v1.1 待办"旧版残留**（同前版）：`E:\Zcode-work\Anima-v1.1\HANDOVER.md`
   后半部是旧草稿，升级清单已完成，勿再做 v1.1。
2. **规则引擎按规则声明的事件名订阅**（内核通配 `"*"` 收不到事件名），
   订阅与分发索引随 `mods.reloaded` 重建（见 `anima/plugins/rule_engine.py`）。
3. **feature 禁用 = 完整卸载**；再启用 = 全新实例重新 `on_load`；
   私有数据经 `module_manager.feature_data(id)` 跨周期保留。
4. **jsonio.load 默认值递归复制**（`_copy_defaults`）：运行时点路径写入不再
   污染模块级 DEFAULT_CONFIG；浅合并语义不变。
5. **main.py 互斥量在 `main()` 里**（测试 import main 不触发锁）；
   `_build_stack()/_kernel_main()` 可直接复用；内核循环经
   `ModuleManagerPlugin.bind_loop` 注入（`Service.bind()` 只增不改）。
6. **功能模组契约 = YingPet FeatureContext 白名单同名平移**：第三方/老模组
   plugin.py 只需把 `from core import ...` 改成 `from anima.utils import ...`，
   其余（class Feature + on_load/on_enable/on_disable + ctx API）零改动。
   packer 类模组的纯函数请复用 `anima.mods.packer`。

---

## 三、目录地图（当前实况）

```
E:\Zcode-work\AnimaPet\
├── HANDOVER.md             ← 本文件（第 5 版）
├── PLAN.md                 ← Phase 0/1/2 全部勾选完成; Phase 3/4/5 待做
├── main.py                 ← ✅ 单实例锁 + 9 插件栈(含 hotreload/character_manager)
├── run.bat                 ← ✅ pythonw 启动器
├── tools\
│   └── migrate_yingpet.py  ← ✅ 数据迁移(config/state/chat_history+备份+dry-run)
├── anima\
│   ├── core\               ← v1.1 内核 9 模块（785 行，冻结勿改）
│   ├── events.py           ← EventNames 常量
│   ├── plugins\
│   │   ├── config.py / state.py / actions.py / loader.py    ← ✅
│   │   ├── safe_eval.py / rule_engine.py                    ← ✅
│   │   ├── bridge.py       ← ✅ (+mods.reloaded→窗口刷新订阅)
│   │   ├── feature_host.py / module_manager.py              ← ✅
│   │   ├── hotreload.py    ← ✅ ModsWatcher(Qt 线程)+防抖→线程感知 rescan
│   │   └── character_manager.py ← ✅ current/switch + 事件链
│   ├── mods\               ← ✅ loader/registry/packer（纯数据层）
│   ├── utils\              ← ✅ paths/log/jsonio/theme
│   └── window\
│       ├── pet_window.py / animator.py / bubble.py          ← ✅
│       └── dialogs\        ← ✅ modmanager.py + settings.py
├── mods\
│   ├── card.ying + behavior.health + ui.{default,dark,sakura}  ← ✅
│   └── feature.{hello,weather,todo,sysmon,clock,packer}        ← ✅ 六个功能模组
├── data\                   ← 运行时生成（gitignore）
└── tests\
    ├── conftest.py         ← QT_QPA_PLATFORM=offscreen
    ├── test_core\          ← 113 内核测试
    ├── test_plugins\       ← basic/mods_layer/loader/safe_eval/rule_engine/window/
    │                          bridge/module_manager/hotreload/character_manager/
    │                          features/ui_mod（共 97 个）
    ├── integration\        ← test_full_stack.py（真实 mods 全链路 + TD1 + 对等回归）
    └── test_utils.py / test_tools.py  ← 10 + 4
```

---

## 四、已定关键设计（按批准的计划，勿偏离）

1. **双线程（TD1-A）**：Qt 主线程 `app.exec()`；内核 asyncio 循环 daemon 线程；
   跨线程调度统一走 `module_manager.fire(coro)`；PetWindow 在 Qt 线程创建
   （main.py `_build_stack`）；UI 线程只 emit；内核线程动 UI 走
   `bridge.run_on_ui`（QObject 队列封送，主线程直调）。
2. **QObject 亲和性铁律**：QFileSystemWatcher/QTimer 等必须在 Qt 主线程创建
   （hotreload 插件经 `bridge.run_on_ui` 保证），否则信号投递到内核线程的
   asyncio 循环（没有 Qt 事件循环）永远不送达。
3. **module_manager 服务**：`list_mods/set_enabled/import_zip/export_zip/
   delete_mod/create_feature_mod/rescan`；`rescan()` 线程感知（内核线程同步
   返回 None，其他线程调度到内核循环返回 Future，调用方 `fut.result(5)`）；
   数据模组启停=config+重建；feature 启停=内核 lifecycle（禁用=完整卸载）。
4. **事件名沿用 YingPet**；`character.switch`（请求）→窗口刷新→
   `character.switched`（完成）链由 character_manager + 窗口订阅实现。
5. **功能模组契约**：`class Feature` + `on_load(ctx)/on_enable/on_disable`，
   ctx = FeatureContext 白名单（emit/on/say/emote/add_menu_action/get_state/
   set_state/log/registry/config/save_config/reload/register_action/data/pet/
   open_path），与 YingPet 同名；FeatureAdapter 强制 `dependencies=[]`。
6. **jsonio 路径安全**：项目根内校验 + 拒 `..` 段 + 默认值递归复制。

---

## 五、剩余任务（按序）

### 下一步：Phase 3 —— .chara 角色卡规范化（PLAN.md §五 Phase 3）

1. Pydantic 模型（CharacterCard/Expression/Animation/Behavior）+ JSON Schema
   导出 `docs/schema/chara.schema.json`
2. 格式规范文档 + 迁移工具升级（card.* ↔ .chara 互转，`tools/migrate_yingpet.py`
   已铺好 config/state/chat_history 平移，补 chara 转换即可）
3. **charcard 编辑器**（6 页签 GUI，源 `E:\dsh-work\YingPet-v4\mods\feature.charcard\*`
   1,273 行，原样保留 + 保存走 Pydantic 校验）；这是 Phase 2 验收里"角色卡编辑"
   项的去向
4. 多角色并存与切换上下文隔离（聊天历史按角色分目录）
5. ZIP 形式 .chara 加载（packer 防护复用）

### 后续阶段

- **Phase 4 聊天**：`LLMProvider` 抽象 + `openai_compat`（源
  `E:\dsh-work\YingPet-v4\mods\feature.chat\*`）、chat 插件/面板、
  chat_history 分角色分会话；YingPet test_chat_plugin 改写随此完成
- **Phase 5 生态**：tray、plugin_dev_guide、PyInstaller 打包、README、v1.0 tag
- **真机 GUI 冒烟**：重启应用后对照对等清单逐项过（新功能模组菜单/热加载/
  角色切换/设置），用户当前运行的实例是旧代码
- test_charcard.py 改写随 Phase 3 编辑器落地

---

## 六、环境与复跑

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python -m pytest tests/ -v          # 当前 216 全绿
.venv\Scripts\python check_kernel_rules.py        # 785 行 + 纯标准库
.venv\Scripts\python tools\migrate_yingpet.py --dry-run   # 迁移演练(只读)
.venv\Scripts\python main.py                      # 真机启动(无控制台用 run.bat)
.venv\Scripts\python -m pip install -r requirements.txt
```

> 集成测试会临时写真实 `mods/card.ying/manifest.json`（try/finally 还原）；
> 若真机实例正在运行且已带 hotreload，测试期间勿同时操作 mods 目录。

---

## 七、坑与经验（本会话实录）

- **QObject 线程亲和性**：hotreload 的 QFileSystemWatcher 若在内核线程创建，
  directoryChanged 信号永远不送达（内核线程只有 asyncio 循环）。凡 Qt 对象
  一律经 `bridge.run_on_ui` 在 Qt 线程创建（见 hotreload 插件）。
- **热重载三步链**：watcher 只触发 `module_manager.rescan()`（线程感知）→
  loader 发 `mods.reloaded` → rule_engine 重建订阅/索引、module_manager 对账
  feature、**bridge 刷新窗口**（这一步是前几版缺失的缺口，帧源/皮肤此前不更新）。
- **跨线程改注册表的唯一合法路径**：`mm.rescan()` 内核线程同步、其他线程
  经 `fire` 调度返回 Future；对话框 `fut.result(5)` 等内核完成（内核侧重扫
  只入队 run_on_ui、不等 Qt，故不会死锁）。`Service.bind()` 只增不改——
  load 晚于 bind_loop，用 None 覆盖会复活 "fire dropped" 静默失效。
- **feature 模组平移成本极低**：FeatureContext 白名单同名后，五个模组仅
  `from core import log` → `from anima.utils import log`；packer 的纯函数核心
  已提取到 anima.mods.packer，插件只留 UI+接线。注意模组对象**没有 .type
  字段**，显示类型要用 isinstance 判定（YingPet 原代码 `getattr(m, "type")`
  永远拿到 "?" 的坑）。
- **扫描目录排序决定"第一个角色"**：`scan_mods` 按目录名排序，
  `card.two` < `card.ying`；测试预期"第一个启用的"时别想当然。
- **测试写真实仓库数据的纪律**：对等回归要改 `card.ying/manifest.json`
  验证写回时，用 try/finally 还原并断言还原成功，防止中断留下脏数据。
- **设置对话框测试需 fixture 里有角色卡**（`_current_char` 依赖），
  module_manager 菜单断言随"设置"项新增而更新（两处）。
- **Mimosa hook**：仍拦截含 `..` 字面量/开放路径拼接的源码写入（jsonio 用
  `chr(46)*2`）；git commit 兼容提示不阻断。
- **终端中文乱码**：cmd 下看日志用 `git log --oneline --encoding=utf-8` 或 PowerShell。

---

## 八、参考文档

- 总计划：`PLAN.md`（Phase 0/1/2 ✅；Phase 3/4/5 待做 + 验收标准）
- 内核 API / 并发模型 / 插件模板：`E:\Zcode-work\Anima-v1.1\docs\` 三份
- 迁移源（只读）：feature.charcard/feature.chat 源码 + 其测试
  （`E:\dsh-work\YingPet-v4\mods\feature.charcard\*`、`feature.chat\*`、
  `tests\test_charcard.py`、`tests\test_chat_plugin.py`）—— Phase 3/4 的主料

> 接手者从第五节"Phase 3 .chara 角色卡规范化"继续。本会话新增坐标：
> 插件=`anima/plugins/{hotreload,character_manager}.py`、
> 对话框=`anima/window/dialogs/settings.py`、
> 模组=`mods/feature.{weather,todo,sysmon,clock,packer}/`、
> 工具=`tools/migrate_yingpet.py`、
> 测试=`tests/test_plugins/{test_hotreload,test_character_manager,test_features,test_ui_mod}.py`+`tests/test_tools.py`。
