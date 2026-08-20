# AnimaPet 开发会话 · 工作交接记录（第 4 版）

> **会话日期**: 2026-08-20（晚间续作）
> **项目**: AnimaPet -- 基于 Anima 内核 v1.1 的桌面宠物元框架
> **位置**: `E:\Zcode-work\AnimaPet`（git 已初始化，按里程碑提交）
> **上游内核**: `E:\Zcode-work\Anima-v1.1`（v1.1 已完成冻结，**只读**，勿改）
> **迁移源**: `E:\dsh-work\YingPet-v4`（只读参考）

---

## 一、当前进度快照（截至本交接）

### 已完成并提交（9 个 commit，全部落地）

| commit | 内容 |
|---|---|
| `8c8a899` | Phase 0 建仓：目录骨架、内核 v1.1 九模块 + 113 个内核测试安置、venv、utils 四件套、events 常量表、10 个 utils 测试 |
| `d6e08e5` | config/state 插件 |
| `36210df` | HANDOVER 第 1 版 |
| `b123852` | actions 插件（ActionRegistry + 内置 state_inc/state_set/emit）|
| `c14866f` | HANDOVER 第 2 版（jsonio 演进/3 个待修测试根因） |
| `901c4f6` | mods 数据层：loader/registry/packer + 真实 mods 数据 + 12 个数据层测试 |
| `5403daf` | loader 插件：扫描->enabled 分流->provide("mods")，rescan 广播 mods.reloaded |
| `0d1e753` | HANDOVER 第 3 版 |
| `d1c276c` | **本会话主体**：rule_engine+safe_eval 插件、window 三件套搬运、bridge 双线程桥、module_manager 总管理器（+feature.hello 改写 + ModsDialog + jsonio 默认值隔离修复 + 39 个新测试） |
| `a8b84e9` | main.py 双线程启动序 + run.bat + 全链路集成测试；PLAN 回填；HANDOVER 第 4 版 |
| `8a6eb8a` | **A 档修复（内核不动）**：loop 注入 module_manager（bind 只增不改）、rescan 线程感知调度（Qt 线程经内核循环 + Future 等待，消竞态）、规则引擎事件索引 + 每事件一次快照（+2 测试，190 全绿） |

### 当前测试状态

```
pytest tests/   →  188 passed
  113 内核 + 10 utils + 7 基础插件 + 12 mods 层 + 4 loader 插件
  + 18 rule_engine/safe_eval + 11 window/bridge + 10 module_manager + 3 集成(全链路)
check_kernel_rules.py → 785 行、纯标准库（过）
main.py offscreen 冒烟 → 20 模组对象 0 错误、规则 7 事件订阅、feature.hello 已加载、
  card.ying 待机/说话帧真实加载(50/60 帧 @180px)、窗口刷新 char=card.ying
```

### 关键里程碑（本会话）

- **TD1 双线程桥落地**：集成测试 `test_td1_cross_thread_run_on_ui` 验证了
  内核线程 → `bridge.run_on_ui` → QObject 队列信号 → Qt 主线程 的真实封送链路。
- **HANDOVER §五 全部任务完成**：rule_engine+safe_eval → window 三件套+bridge
  → module_manager（zip-slip/冲突改名/删除复活/运行时启停四项专项全绿）→
  main.py 启动序 + 全链路集成测试 + PLAN.md 回填（本文件 = 交接记录）。
- **PLAN Phase 1 全部 9 项勾选完成**；Phase 2 完成第 2、4 项（rule_engine、
  module_manager），剩 hotreload/character_manager/五模组改写/迁移工具/测试改写。

---

## 二、重要澄清（避免接手者踩坑）

1. **HANDOVER 里的"v1.1 待办"是旧版残留**（同第 3 版）：`E:\Zcode-work\Anima-v1.1\HANDOVER.md`
   后半部是旧草稿，"v1.1 升级清单"已完成。勿再做 v1.1。
2. **规则引擎订阅方式与第 3 版交接的表述不同**：内核总线通配订阅 `"*"` 的
   handler **收不到事件名**（`emit` 只传 payload），而规则匹配需要事件名。
   因此规则引擎**按规则声明的 on 事件名逐个订阅**（语义与 on_all+过滤完全
   等价，且更省开销），订阅随 `mods.reloaded` 差量重建。见
   `anima/plugins/rule_engine.py` 头部注释。
3. **feature 禁用 = 完整卸载**：`set_enabled(feature, False)` 走
   `lifecycle.disable + unload`（副作用全回滚、菜单移除）；再启用 =
   全新实例重新 `on_load`。私有数据经 `module_manager.feature_data(id)`
   跨周期保留（等价 YingPet `_feature_data`）。
4. **jsonio.load 浅合并已隔离默认值**：旧实现 `dict(default)` 浅拷贝导致
   嵌套 dict 与模块级 `DEFAULT_CONFIG` 共享，运行时点路径写入会污染后续
   load 的默认值（本会话测试互相污染暴露）。现 `_copy_defaults` 递归复制，
   浅合并语义不变（`test_jsonio_load_dict_shallow_merge` 仍过）。
5. **main.py 互斥量在 `main()` 里调用**（不在模块级）：测试 import main
   不会触发单实例锁；`_build_stack()/_kernel_main()` 可直接复用。

---

## 三、目录地图（当前实况）

```
E:\Zcode-work\AnimaPet\
├── HANDOVER.md             ← 本文件（第 4 版）
├── PLAN.md                 ← 总计划（Phase 1 已全勾选；Phase 2 完成 2/4 项）
├── main.py                 ← ✅ 单实例锁 + Qt 主线程 + 内核 asyncio daemon 线程(TD1-A)
├── run.bat                 ← ✅ pythonw 启动器(venv 探测链, 纯 ASCII)
├── pyproject.toml / requirements.txt / check_kernel_rules.py / .gitignore
├── .venv\                  ← Python 3.13.0
├── anima\
│   ├── core\               ← v1.1 内核 9 模块（785 行，冻结勿改）
│   ├── events.py           ← EventNames 常量（含 plugin.enabled/disabled）
│   ├── plugins\
│   │   ├── __init__.py
│   │   ├── config.py       ← ✅ ConfigPlugin（构造可注入 service, 与窗口共享实例）
│   │   ├── state.py        ← ✅ StatePlugin（同上）
│   │   ├── actions.py      ← ✅ ActionsPlugin（同上）
│   │   ├── loader.py       ← ✅ LoaderPlugin（provide "mods" + "loader" 服务）
│   │   ├── safe_eval.py    ← ✅ 248 行原样搬（白名单条件求值）
│   │   ├── rule_engine.py  ← ✅ 按规则事件名订阅 + actions 服务执行 + @idle.this
│   │   ├── bridge.py       ← ✅ TD1 双线程桥（run_on_ui 队列封送/表现 API/菜单登记）
│   │   ├── feature_host.py ← ✅ FeatureContext 白名单 + FeatureAdapter(deps=[])
│   │   └── module_manager.py ← ✅ 总管理器服务 + 对账 + zip 导入导出/删除/新建
│   ├── mods\               ← ✅ loader.py/registry.py/packer.py（纯数据层无 Qt）
│   ├── utils\              ← ✅ paths/log/jsonio/theme（jsonio 默认值隔离）
│   └── window\
│       ├── pet_window.py   ← ✅ 构造注入改造（registry/bus/config/state/actions/engine）
│       ├── animator.py     ← ✅ 近原样搬
│       ├── bubble.py       ← ✅ 近原样搬
│       └── dialogs\        ← ✅ modmanager.py（ModsDialog/NewRuleTemplateDialog/导入动画）
├── mods\                   ← ✅ card.ying + behavior.health + ui.{default,dark,sakura} + feature.hello
├── data\                   ← 运行时生成（config.json/state.json/pet.log，gitignore）
└── tests\
    ├── conftest.py         ← ✅ QT_QPA_PLATFORM=offscreen（PyQt6 首次导入前设定）
    ├── test_core\          ← ✅ 113 个内核测试
    ├── test_plugins\       ← ✅ basic(7)/mods_layer(12)/loader_plugin(4)/
    │                          safe_eval(8)/rule_engine(10)/window(8)/bridge(3)/module_manager(10)
    ├── test_window\        ← ⬜ 空
    ├── integration\        ← ✅ test_full_stack.py（真实 mods 全链路 + TD1 跨线程）
    └── test_utils.py       ← ✅ 10 个
```

---

## 四、已定关键设计（按批准的计划，勿偏离）

1. **双线程（TD1-A）**：Qt 主线程 `app.exec()`；内核 asyncio 循环 daemon 线程；
   `run_coroutine_threadsafe` 不直接暴露给插件——`module_manager.fire(coro)`
   统一调度（内核线程 create_task / Qt 线程 run_coroutine_threadsafe）。
   PetWindow 在 Qt 线程创建（main.py `_build_stack`），引用传给 BridgePlugin。
   UI 线程只 emit；内核线程动 UI 走 `bridge.run_on_ui`
   （QObject + pyqtSignal(object) 队列封送；已在 Qt 主线程则直调）。
2. **插件总管理器 module_manager**：服务 API `list_mods()/set_enabled(id,on)/
   import_zip(path)/export_zip(id,path)/delete_mod(id)/create_feature_mod(id,name)/
   rescan()`（async 核心 + fire 门面两层）。数据模组启停=写 config.mods.enabled+
   loader.rescan 重建；feature 启停=内核 lifecycle（禁用即完整卸载）；新增=
   `load_all([FeatureAdapter])+enable`；删除=unload+rmtree。适配器强制
   `dependencies=[]`。zip 导入导出走 `anima.mods.packer`（Zip-Slip 三重拒绝、
   id_2 冲突改名回写 manifest、`__pycache__/.pyc` 过滤、失败 rmtree 回滚）。
3. **事件名沿用 YingPet**（行为模组 rules 兼容），已加 plugin.enabled/disabled。
4. **jsonio 路径安全**：项目根（`_BASE`）内校验 + 拒 `..` 段；`PathGuardError`
   区分路径拒绝与 JSON 解析失败；`load` 的默认值递归复制（隔离模块级默认）。
5. **服务共享模式**：main.py 先建 ConfigService/StateService/Registry/
   ActionRegistry 实例，插件构造与 PetWindow 共用（插件构造器均可选注入）。
6. **FeatureContext 契约与 YingPet 同名保留**：feature 模组 plugin.py 仍是
   `class Feature` + `on_load(ctx)/on_enable/on_disable`；ctx.emit/on/say/emote/
   add_menu_action/get_state/set_state/log/registry/config/save_config/reload/
   register_action/data/pet/open_path 全部等价保留（feature.hello 已按此改写）。

---

## 五、剩余任务（按序）

### 下一步：hotreload 插件（PLAN Phase 2 第 1 项）

- `anima/plugins/hotreload.py`：QFileSystemWatcher + 800ms 防抖，编排照搬
  YingPet harness（`_refresh_watch_paths/_on_fs_changed/_do_debounced_reload`），
  但 reload 动作改调 `loader.rescan()` + `module_manager.sync_features()` +
  `bridge.run_on_ui(pet.refresh_from_registry)` + 菜单同步（bridge 已持久登记，
  feature 重新 on_load 会自动重放，无需额外逻辑）。
- 专项测试：拖入新模组 → 1 秒内生效；坏模组自动降级不崩；热重载后
  feature 私有数据（`feature_data`）不丢。

### 后续任务（继续按 PLAN Phase 2 顺序）

- **character_manager 插件**（第 3 项）：card 生命周期、active 切换、
  归属过滤、`character.switched` 事件链（窗口 `_switch_character` 目前已内联
  完成等价功能，抽取成插件时保持事件兼容）。
- **五个功能模组改写**（第 5 项）：weather/todo/sysmon/clock/packer，契约照
  feature.hello（FeatureContext API 平移），源坐标 `E:\dsh-work\YingPet-v4\mods\feature.*`；
  QThread 采样器保留，`ctx.say/emote` 走 bridge。
- **tools/migrate_yingpet.py**（第 6 项）+ YingPet 6 个测试文件改写 + 热重载专项（第 7 项）。
- 真机 GUI 冒烟：双击 `run.bat` 或 `python main.py`，对照 PLAN Phase 1 验收
  逐项过（点击/拖拽/双击/右键表情/切皮肤/大小/久坐开关/退出）。
- 后续阶段：Phase 3 .chara / Phase 4 聊天 / Phase 5 tray+打包（见 PLAN.md）。

---

## 六、环境与复跑

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python -m pytest tests/ -v          # 当前 188 全绿
.venv\Scripts\python check_kernel_rules.py        # 785 行 + 纯标准库
.venv\Scripts\python main.py                      # 真机启动（无控制台用 run.bat）
.venv\Scripts\python -m pip install -r requirements.txt   # 重建环境时
```

> 注意：集成测试与 main.py 冒烟会读写 `data/`（gitignore）并可能在 `mods/`
> 无写操作（集成测试只读真实 mods）；跑 GUI 前若桌面右下角已有实例，
> 单实例锁会直接退出。

---

## 七、坑与经验（本会话实录）

- **跨线程改注册表的唯一合法路径**：`module_manager.rescan()` 线程感知——内核线程
  同步执行并返回 None，其他线程经 `fire` 调度到内核循环并返回 Future
  （对话框 `fut.result(5)` 等待；内核侧重扫不依赖 Qt 泵事件，不会死锁）。
  `fire` 依赖内核循环注入：main.py 在 `_kernel_main` 里 `plugin.bind_loop(loop)`，
  且 `Service.bind()` **只增不改**（load 晚于 bind_loop，用 None 覆盖会复活
  "fire dropped" 静默失效）。
- **规则引擎分发索引**：`refresh()` 重建 `{事件名: [(mod, idx, rule)]}`，
  `_handle` 只遍历命中项；state/event/config 快照每事件懒建一次。
- **内核总线通配订阅收不到事件名**：`EventBus.emit(event, data)` 只把 data
  传给 handler。规则引擎因此改按 `on` 事件名逐个订阅；任何需要事件名的
  监听场景都要走显式订阅（见二.2）。
- **jsonio.load 浅合并共享嵌套默认 dict**：运行时 `config.set("window.size", ...)`
  会写进模块级 DEFAULT_CONFIG，测试互相污染（display_size 320≠180 就是这么
  暴露的）。已用 `_copy_defaults` 递归复制修复——**新加多层默认配置时勿再
  退化成 dict(default)**。
- **loader 插件要 provide 两个服务**：`"mods"`（注册表）与 `"loader"`
  （插件自身，module_manager 经它调 rescan）。只 provide 注册表会让
  `use("loader")` 返回 None。
- **feature 启停用完整卸载**：若只 disable 不 unload，再 enable 时菜单/订阅
  不会重放（on_load 只跑一次），行为与 YingPet 不一致；完整卸载让
  EffectTracker 自动回滚订阅，重启用全新实例最干净。
- **feature 适配器的 name 用 @property 返回模组 id**：FeatureAdapter 是
  Plugin 子类，`name`/`dependencies` 用 property 覆写类属性；`dependencies=[]`
  是硬要求（HANDOVER §四.2）。
- **Qt offscreen 测试三件套**：`tests/conftest.py` 顶层先 `os.environ.setdefault
  ("QT_QPA_PLATFORM","offscreen")`（必须早于任何 PyQt6 import）；QApplication
  用 module-scope fixture（`QApplication.instance() or QApplication([])`）；
  窗口测试在 tmp 造 Registry/ConfigService/StateService，不用真 mods。
- **集成测试的 jsonio 守卫**：真实 mods 在 E: 盘、pytest tmp 在 C: 盘，一个
  `_BASE` 罩不住两边，fixture 里 monkeypatch `jsonio._guard` 为放行版（只影响
  该测试）。
- **跨线程 run_on_ui 验证要泵事件**：offscreen 下主线程没有 app.exec()，
  队列信号用 `qapp.processEvents()` 手动泵（见 test_td1_cross_thread_run_on_ui）。
- **Mimosa hook 拦截含 `..` 字面量/开放路径拼接的源码写入**（同前版）：
  jsonio 用 `chr(46)*2` 构造；git commit 触发兼容提示不阻断提交。
- **终端中文乱码**：cmd 下 git log 中文 commit 显示乱码是 GBK 终端问题，
  看日志用 `git log --oneline --encoding=utf-8` 或换 PowerShell。

---

## 八、参考文档

- 总计划：`PLAN.md`（TD1-TD6 决策、迁移映射表、Phase 验收标准；Phase 1 已勾选）
- 内核 API：`E:\Zcode-work\Anima-v1.1\docs\core_api.md`（冻结接口）
- 内核并发模型：`E:\Zcode-work\Anima-v1.1\docs\architecture.md` 第 7 节
  （UI 线程只 emit、订阅只在内核线程——bridge 设计的依据）
- 插件开发模板：`E:\Zcode-work\Anima-v1.1\docs\maintenance.md` 第 10 节
- 迁移源（只读）：window/animator/bubble 已搬；hotreload 编排参考
  `E:\dsh-work\YingPet-v4\core\harness.py` 的 watcher 段；五功能模组参考
  `E:\dsh-work\YingPet-v4\mods\feature.*`

> 接手者从第五节"hotreload 插件"继续。本会话新增文件坐标：
> 插件=`anima/plugins/{safe_eval,rule_engine,bridge,feature_host,module_manager}.py`、
> 窗口=`anima/window/{pet_window,animator,bubble}.py`+`dialogs/modmanager.py`、
> 入口=`main.py`/`run.bat`、模组=`mods/feature.hello/`、
> 测试=`tests/integration/test_full_stack.py`+test_plugins 5 个新文件。
