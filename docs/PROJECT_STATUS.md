# AnimaPet 项目结项报告

> 记录时间：2026-08-23
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