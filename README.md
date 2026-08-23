# AnimaPet

基于 Anima 内核 v1.1.1 的 Windows 桌面宠物元框架。
数据格式沿用 YingPet-v4 的 card.* 角色卡与行为规则, 在 Anima 插件内核上重新组织:
事件总线 + asyncio 内核线程 + Qt 主线程双线程模型, 官方插件/mod 全部可热重载。

## 功能

- **角色卡(.chara)**: 人设/动画/台词/行为/表情自包含, 支持 zip 拖装与 6 页签编辑器;
- **行为规则**: `when/if/cooldown/then` + safe_eval, 与 YingPet 规则 100% 兼容;
- **多角色**: 切换隔离(人设/行为/聊天历史按角色分目录);
- **聊天(Phase 4)**: OpenAI/DeepSeek 兼容适配器, 系统人设注入 + emotion 白名单,
  按角色历史存储/搜索/单条删除/JSON 导入导出;
- **功能模组**: 菜单/事件/状态白名单 `FeatureContext`, 热重载即改即生效;
- **一切皆插件(方案 A)**: 角色卡管理器与聊天窗口本身也是 `mods/feature.*` 内置功能模组,
  可在「模组管理」里启停/删除/替换, 而不只是框架内硬编码入口;
- **系统托盘(Phase 5)**: 角色/皮肤快速切换 + 退出;
- **日志导出**: 模组管理里有「导出日志…」「打开日志文件夹」(data/pet.log);
- 皮肤主题、天气/待办/时钟/系统监控/打包导入导出等模组沿用 YingPet-v4。

## 运行

```bash
cd E:\Zcode-work\AnimaPet
.venv\Scripts\python main.py        # 源码运行
run.bat                             # pythonw 无控制台启动
```

首次运行会自动生成 data/; 右键宠物可打开「角色卡管理器」「聊天窗口」等入口。
发布前真机验证清单见 `docs/RELEASE_CHECKLIST.md`。

## 测试

```bash
.venv\Scripts\python -m pytest tests/ -q          # 当前 253 passed
.venv\Scripts\python check_kernel_rules.py        # 内核铁律检查(840 行/纯标准库)
.venv\Scripts\python tools\export_chara_schema.py # 重新生成 .chara JSON Schema
```

## 打包与性能

```bash
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python tools\build_exe.py          # 生成 dist/AnimaPet/ (onedir)
.venv\Scripts\python tools\benchmark.py          # offscreen 启动/内存基准
```

| 基准 | 实测(offscreen) | 目标 |
|---|---|---|
| 全栈启动 | 1.520 s | < 3 s ✅ |
| Python 峰值内存 | 6.5 MiB | 与 YingPet 持平(待真机对比) |

## 开发

- 官方插件: `anima/plugins/`(config/state/actions/loader/bridge/rule_engine/...),
  服务经 `app.registry.use("服务名")` 获取;
- 第三方功能模组: 见 `docs/plugin_dev_guide.md`; 脚手架:
  `.venv\Scripts\python tools\new_plugin.py greet 问候`;
- .chara 角色卡开发: `docs/chara_dev_guide.md`; 格式规范: `docs/chara_format.md`;
- 用户使用: `docs/user_guide.md`; 发布检查: `docs/RELEASE_CHECKLIST.md`;
- 项目结项报告: `docs/PROJECT_STATUS.md`;
- JSON Schema: `docs/schema/chara.schema.json`;
- 迁移工具: `.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run`。

## 进度

| 阶段 | 状态 |
|---|---|
| 0 内核安置 | ✅ |
| 1 最小可运行宠物 | ✅ |
| 2 业务全插件化 | ✅ |
| 3 .chara 规范化 | ✅ |
| 4 聊天与多 LLM | ✅(真机 LLM 联调待用户环境) |
| 5 生态与收尾 | ✅(tray/文档/打包/性能基准/tag v1.0) |

## 目录

```text
anima/          官方内核/插件/模型/适配器/窗口
mods/           用户模组(card/feature/ui/...)
tools/          迁移/schema/脚手架工具
docs/           格式规范/开发指南/schema
tests/          253 个测试(内核/插件/集成)
data/           运行时配置/状态/日志(不入库)
```