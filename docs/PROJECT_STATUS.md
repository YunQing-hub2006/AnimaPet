# AnimaPet 项目结项报告

> 记录时间：2026-08-23（v1.0 收尾存档）
> 最近更新：2026-08-28（结项后追加两轮：§9 UI/可维护性重构、§10 新手功能轮）
> 项目定位：基于 Anima 内核 v1.1.1 的 Windows 桌面宠物元框架（个人项目，已按当前阶段收尾存档）
> 结论：**代码与测试已完成到 v1.0，但未经真机持续使用验证，项目按“暂缓/存档”处理。**

---

## 1. 项目背景与目标

将 YingPet-v4（约 6,681 行 Python 的桌面宠物）迁移到自研的 Anima 插件内核上，
核心设计是：

1. **一切皆插件**：用户可见功能（角色卡编辑器、聊天、天气、待办……）都应是可删、可换、可热重载的模组；
2. **内核不动**：Anima 内核责任单一（事件总线/插件生命周期/服务注册），业务全部在插件层；
3. **数据格式继承**：沿用 YingPet `card.*` 角色卡结构，规范化为 `.chara`，与聊天历史按角色隔离。

---

## 2. 最终交付物

| 交付物 | 状态 |
|---|---|
| Anima 内核 v1.1.1（840 行纯标准库，冻结） | ✅ |
| PLAN Phase 0-5 全部代码 | ✅ |
| 自动化测试 | ✅ 254 passed |
| 角色卡 `.chara` 格式 + JSON Schema + 编辑器 | ✅ |
| 聊天与多 LLM（OpenAI/DeepSeek 兼容） | ✅ 代码完成，真机联调未做 |
| 系统托盘、日志导出、新建功能模组入口 | ✅ |
| 开发/使用文档 | ✅ 4 份指南 + 结项报告 |
| PyInstaller 打包 | ✅ `dist/AnimaPet/AnimaPet.exe`（onedir，含 mods） |
| Git tag | ✅ `v1.0` |

**未完成/未验证**：

- 真机持续使用验证（用户侧）未进行；
- 聊天 API 实际联网联调未做（依赖 API key 与网络）；
- exe 无自定义图标/版本信息/单文件版；
- 性能内存与 YingPet 实测对比未做（offscreen 启动 1.520s / Python 峰值 6.5 MiB）。

---

## 3. 核心架构与关键决策

### 3.1 双线程模型（TD1-A）

- Qt 占主线程，Anima asyncio 内核跑在后台 daemon 线程；
- `bridge.run_on_ui` 是唯一合法跨线程 UI 通道；
- 功能模组白名单新增 `ctx.task` / `ctx.run_on_ui` / `ctx.use`，确保第三方也能写 UI+异步插件。

### 3.2 校验边界分工

- `anima.models.load_card/save_card`：整体校验（编辑器/工具保存把关，坏数据明确报错）；
- `loader._build_card`：运行时逐文件降级（坏项丢弃，其余照常，绝不因坏数据崩）。

### 3.3 .chara 规范化（TD4）

- 物理结构 = YingPet `card.*` 文件夹 + `manifest.format="chara-1"`；
- 表情双名兼容（`emotes` ↔ `expressions`）；
- id 统一 `card.` 前缀 + 字符集归一；zip 导入带 Zip-Slip 防护。

### 3.4 方案 A：一切皆插件的最后一块拼图

- 角色卡管理器、聊天窗口从“框架硬编码”下放为 `mods/feature.charcard/`、`mods/feature.chat/`；
- 总管理器（module_manager）现在能对它们启停、删除、替换；
- 新增「模组管理 → 新建… → 新建功能模组…」，用户可从 UI 创建自定义模组。

---

## 4. 项目规模

```text
anima/           框架（内核/插件/模型/适配器/窗口）
mods/            11 个功能模组 + 角色卡 + 3 皮肤（含内置 feature.chat/charcard）
docs/            使用/开发/.chara/发布清单/结项报告
tools/           迁移/schema/脚手架/打包/benchmark
tests/           254 个测试（内核/插件/集成）
dist/            打包产物（gitignore，不入库）
```

### 提交链（简）

```text
8c8a899 Phase 0 建仓
…                Phase 1/2 基础设施与插件化
ab239e9 内核升级 v1.1.1
6617f5e Phase 3 数据层
380b8df Phase 3 编辑器/测试/文档
b7f56ef Phase 4 聊天与多 LLM
e7744af Phase 5 托盘/指南/骨架
e5ac527 方案 A：内置功能模组化
244bd8e 新建功能模组入口
d35e9d4 Phase 5 打包/性能/README
bc0107e 日志导出
48993ad HANDOVER v10 + 发布清单
a8672c1 三份指南
tag: v1.0
```

---

## 5. 踩过的坑（经验记录）

1. **packer 归一分支**：`chara→card` 类型/id 归一在无目录冲突时不会回写 manifest，
   需用 `raw_id` 比较并强制回写；
2. **migrate 历史分流**：`chat_history[<id>]` 计划项未按前缀匹配，被当字符串写坏；
3. **Qt 线程调 async**：UI 信号里不能 `asyncio.ensure_future`，统一走 `module_manager.fire`；
4. **FeatureContext 扩展**：官方功能下放为 mod 后，必须补 `task/run_on_ui/use` 白名单能力；
5. **配置注入时机**：测试里先 `cfg.set` 不落盘会被 `ConfigPlugin.load` 覆盖，要先 `cfg.save()`；
6. **Mimosa hook**：仓库内写文件走 `jsonio.save`（项目根白名单 + 原子写）。

---

## 6. 为什么没有继续推进

按原计划，发布前只剩：

- 真机冒烟（`docs/RELEASE_CHECKLIST.md` 已备好）；
- 确认后删除 `E:\Zcode-work\Anima-core-old\core` 归档；
- 可选：exe 图标/单文件版/签名。

由于项目被认为“没有实际使用价值”，开发在此收尾。**代码与文档保留在仓库中，作为存档与未来参考**。

---

## 7. 未来若要复用/重启

1. 跑真机冒烟清单，修问题后即可作为个人工具使用；
2. 若想换方向，最有复用价值的是：
   - `.chara` 角色卡格式 + JSON Schema；
   - FeatureContext 插件契约与热重载模型；
   - 双线程（Qt + asyncio）桥接范式；
   - 按角色隔离的数据目录约定。
3. 快速验证命令：

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python -m pytest tests/ -q
.venv\Scripts\python tools\benchmark.py
.venv\Scripts\python tools\build_exe.py
run.bat
```

---

## 8. 一句话总结

AnimaPet 完成了“从 YingPet 单机项目 → 插件化桌面宠物元框架”的迁移，
代码质量与自动化测试完整，但作为产品缺少真实用户验证；当前以 v1.0 存档，
源代码、格式规范、开发文档与打包产物均已就位。

---

## 9. 附录：2026-08-28 UI/可维护性重构轮（结项后追加）

> 触发原因：结项后复查发现 UI 层三类问题 —— ① 四个对话框各自维护一份白色
> QSS，与主界面深紫配色割裂；② `wait_fire`/PNG 导入等逻辑存在 2~3 份拷贝；
> ③ 聊天历史逐条渲染、动画定时器空转等性能问题。
> 本轮**只动表现层与重复实现，不改任何行为契约**（事件名/信号/存储格式/插件接口全部不变）。

### 9.1 改动清单

| 类别 | 改动 | 涉及文件 |
|---|---|---|
| 主题统一 | `theme.py` 升级为主题设计系统：颜色单点定义 + `menu_qss()/dialog_qss()/panel_qss()` 样式工厂；四个对话框从白底换统一暗色主题 | `utils/theme.py`、`settings.py`、`modmanager.py`、`charcard/dialog.py`、`charcard/wizard.py` |
| 去重 | 新建 `window/dialogs/common.py`：收拢 3 份 `wait_fire`/`wait_rescan` 与 2 份动画 PNG 导入；`charcard/__init__` 保留再导出兼容 | `dialogs/common.py`（新增）、`modmanager.py`、`charcard/*` |
| 对话框合并 | modmanager 两个“新建模组”对话框合并为 `_NewModDialogBase` 基类（id 校验/冲突检查共用） | `modmanager.py` |
| 聊天面板 | 工具栏重组（导出/导入收进“备份 ▾”菜单）；历史回放/搜索/会话浏览改批量渲染（一次文档重排）；空历史显示新手引导；消息 HTML 标记收进 ChatPanel，`plugins/chat.py` 只传数据；状态栏不再靠字符串切割拼装 | `window/chat_panel.py`、`plugins/chat.py` |
| 设置对话框 | 改两步向导式（① 对话模型 ② 角色人设），字段带悬停说明，温度改 0~2 滑条 | `settings.py` |
| 性能 | Animator 帧定时器按需启停（无可画帧不空转，表情/动画播放自动唤醒）；聊天面板 20+ 次 `setStyleSheet` 合并为 1 次 | `window/animator.py`、`chat_panel.py` |
| 清理 | PetWindow 菜单构建拆出 `_populate_menu` 并走主题工厂；tray `_quit` 等小清理 | `pet_window.py`、`tray.py` |

### 9.2 验证

- 全量测试 **254 passed**（唯一测试改动：设置对话框温度字段改滑条后，
  `test_settings_dialog_saves_config_and_char_prompt` 同步驱动 `sld_temp`）；
- `python -m compileall` 全量通过；
- 离屏实例化宠物窗口/聊天面板/设置/模组管理/角色卡管理器并截图检查，
  布局与配色正常（offscreen 平台缺 CJK 字体，截图文字显示为方块属环境限制）；
- 专项验证 `clicked(bool) → 零参信号 .emit` 与 `QMenu.addAction(text, slot)` 两条信号链安全。

### 9.3 规模与状态

- 13 个文件修改 + 1 个新增（`anima/window/dialogs/common.py`），+616/−535 行；
- **改动停留在工作区，尚未提交**；真机冒烟（`docs/RELEASE_CHECKLIST.md`）在本轮之后仍待执行；
- 皮肤模组（ui.*）兼容性：`merge_theme` 键集合未变，旧皮肤直接可用。

---

## 10. 附录：2026-08-28 功能轮（同日第二轮，面向新手）

> 目标：不懂代码的用户也能完成四件以前要写 JSON/摆弄文件夹的事 —— 导入聊天记录、
> 配行为规则、做皮肤、导 GIF 动画。测试 254 → **263 passed**（新增 9 个）。

### 10.1 新功能

| 功能 | 说明 | 落点 |
|---|---|---|
| 聊天记录导入增强 | 「备份▾ → 从 JSON 恢复」弹出三选：**合并(保留现有+按内容去重) / 覆盖现有 / 取消**；合并时会话号紧凑顺延不冲突 | `plugins/chat.py`（HistoryStore.import_json 加 mode 参数） |
| 行为规则可视化编辑 | 角色卡管理器·行为页签重做：触发事件改**中文下拉**（摸头/拖动/闲置/深夜/聊天回复等 9 种 + 自定义），动作改为**搭建器**（说话/表情/动画三选一，台词下拉提示 `@idle.this.<段>`，支持增删/上移/下移），保存前强制"至少一个动作"并给新手话术提示；规则列表显示人话（“#1 被摸头 → 2 个动作·冷却5s”）；高级用户保留「编辑选中规则 JSON…」出口 | `window/dialogs/charcard/dialog.py` |
| 皮肤工坊（新功能模组） | 右键菜单新入口：从默认/现有皮肤起步，19 个配色项分组取色，**实时预览**迷你聊天窗，保存生成 `mods/ui.<id>/`（与手写皮肤同构），可勾选"保存后立即换上" | `window/dialogs/skinmaker.py` + `mods/feature.skinmaker/`（manifest+plugin，仿 charcard 门面模式） |
| GIF 导入 | GIF 自动解帧为 PNG 序列：模组管理「新建▾ → 导入 GIF 动画到素材库」、角色卡管理器「动画页签 → 导入 GIF 到本卡」「素材库页签 → 导入 GIF 到素材库」；用 QImageReader 解码（Qt 自带 GIF 支持，**零新依赖**），帧延时折算 fps（1~30），单 GIF 上限 600 帧 | `window/dialogs/common.py`（extract_gif_frames/import_gif）+ `charcard/assets.py`（import_gif_to_card） |

### 10.2 测试

- 更新：`test_full_stack`（真实 mods 计数 27→28、features 8→9）、
  `test_charcard` 行为写回改驱动新表单；
- 新增 9 个：`test_gif_import`(4：解帧/坏文件/素材库模组/卡内导入)、
  `test_skinmaker`(3：保存并应用/冲突与非法 id 拒绝/现有皮肤起步)、
  `test_chat_plugin` 合并导入(1)、`test_charcard` 自定义事件+JSON 出口(1)；
- 离屏截图验证行为页与皮肤工坊布局正常。

### 10.3 兼容性说明

- `HistoryStore.import_json(path)` 旧调用（无 mode）等价 overwrite，行为不变；
- 手写 ui.* 皮肤、behavior 规则 JSON 格式完全不变（可视化编辑只是它们的生成器）；
- 真机冒烟清单仍待执行（§9.3 同）。