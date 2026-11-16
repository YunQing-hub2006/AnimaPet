# AnimaPet

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 Anima 内核 v1.3.1 的 Windows 桌面宠物元框架。
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
cd AnimaPet
.venv\Scripts\python main.py        # 源码运行
run.bat                             # pythonw 无控制台启动
```

首次运行会自动生成 data/; 右键宠物可打开「角色卡管理器」「聊天窗口」等入口。
发布前真机验证清单见 `docs/RELEASE_CHECKLIST.md`。

## 测试

```bash
.venv\Scripts\python -m pytest tests/ -q          # 当前 346 passed
.venv\Scripts\python tools\check_kernel_rules.py  # 内核检查: 纯标准库 + core 行数
.venv\Scripts\python tools\export_chara_schema.py # 重新生成 .chara JSON Schema
```

> ⚠️ `check_kernel_rules.py` 的行数断言（`anima/core` < 1000 行）**目前会失败**：
> 内核升到 v1.3.1 后为 1197 行（v1.1.1 时 840 行）。纯标准库那部分检查是通过的。
> 这是内核升级带来的既存漂移，阈值是否放宽待内核侧决定。

## 打包与性能

```bash
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python tools\build_exe.py          # 生成 dist/AnimaPet/ (onedir)
.venv\Scripts\python tools\benchmark.py          # offscreen 启动/内存基准
.venv\Scripts\python tools\bench_anim.py         # offscreen 动画渲染基准(解码/重绘次数)
```

| 基准 | 实测(offscreen) | 目标 |
|---|---|---|
| 全栈启动 | 1.520 s | < 3 s ✅ |
| Python 峰值内存 | 6.5 MiB | 与 YingPet 持平(待真机对比) |

> 上表为 2026-08-23 口径。2026-08-30 的优化轮把 `dist/AnimaPet/` 从 286MB 降到 155MB、
> 单张表情加载峰值从 16.52MB 降到 0.89MB，详见 `docs/PROJECT_HISTORY.md` §17。
> `dist/` 与 `build/` 是可再生产物，未入库；按上面的命令随时重建。

## 开发

- 官方插件: `anima/plugins/`(config/state/actions/loader/bridge/rule_engine/...),
  服务经 `app.registry.use("服务名")` 获取;
- 第三方功能模组: 见 `docs/plugin_dev_guide.md`; 脚手架:
  `.venv\Scripts\python tools\new_plugin.py greet 问候`;
- .chara 角色卡开发: `docs/chara_dev_guide.md`; 格式规范: `docs/chara_format.md`;
- 用户使用: `docs/user_guide.md`; 发布检查: `docs/RELEASE_CHECKLIST.md`;
- 内核更换/升级记录: `docs/kernel_upgrade.md`;
- 项目历史总档案(背景/技术决策 TD1-TD6/迁移映射/踩坑/优化轮): `docs/PROJECT_HISTORY.md`;
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
tools/          迁移/schema/脚手架/打包/内核铁律检查
docs/           格式规范/开发指南/使用指南/项目历史/schema
tests/          346 个测试(内核/插件/集成)
data/           运行时配置/状态/日志(不入库)
dist/ build/    打包产物(可再生产物, 不入库)
```

## 开源说明

### 许可

- 本项目**软件代码**采用 [MIT License](LICENSE) 开源。
- 项目内附带的**角色卡与美术素材**版权归各自权利人所有，**不受 MIT 许可覆盖**，
  详见下方「素材版权」与各 `mods/card.*/NOTICE.md`。

### 项目结构

```
AnimaPet/
├── main.py             入口：单实例锁 → Qt 应用 → 内核线程装配 → 启动/停止
├── anima/              框架代码
│   ├── core/           内嵌 Anima 插件内核（v1.3.1，纯标准库）
│   ├── plugins/        官方插件（config/state/chat/rule_engine/loader/bridge…）
│   ├── mods/           模组数据层（加载器/注册表/打包导入导出）
│   ├── models/         角色卡/聊天数据模型（Pydantic）
│   ├── adapters/       OpenAI 兼容 LLM 适配器
│   ├── window/         Qt 渲染层（宠物窗口/气泡/对话框/托盘）
│   └── utils/          路径/JSON/日志/主题工具
├── mods/               随项目分发的模组与角色卡
│   ├── card.ying/      同人角色卡「影」（见 NOTICE.md，非官方同人）
│   ├── card.dsh/       角色卡「鲸鱼娘」（素材来自 dsh-pet，MIT，见 NOTICE.md）
│   ├── feature.*/      功能模组（chat/charcard/weather/todo/clock…）
│   └── ui.*/           皮肤主题模组
├── tools/              开发/打包/迁移/基准工具
├── docs/               格式规范/开发指南/使用指南/项目历史/JSON Schema
├── tests/              测试（内核/插件/集成，约 346 个）
├── character-cards/    导出的 .chara 角色卡压缩包（交付物）
├── LICENSE             MIT 许可（仅覆盖代码）
└── .gitignore          忽略规则（data/、构建产物、密钥、工具状态）
```

### 使用注意事项

1. **环境**：Windows + Python >= 3.11；GUI 依赖 PyQt6（`pip install -r requirements.txt`）。
   仓库内的 `.venv` 为本地开发目录，未随仓库分发，请自行创建。
2. **首次运行**：自动在 `data/` 生成配置/状态/日志；`data/` 已被 git 忽略，
   其中可能包含你填写的 LLM API key（以明文存于 `data/config.json`）——
   **切勿提交或分享该文件**。建议使用环境变量或本地密钥管理。
3. **聊天功能**：需自行在设置中填写 OpenAI/DeepSeek 兼容的 API 地址与密钥；
   未配置时角色会使用卡内本地台词降级回复，不影响其他功能。
4. **测试**：`python -m pytest tests/ -q`。集成测试中依赖真实角色素材的部分，
   在本地保留 `mods/card.ying/` 与 `mods/card.dsh/` 时正常执行。
5. **打包**：`tools/build_exe.py` 生成 `dist/AnimaPet/`（onedir），属可再生产物，不入库。

### 素材版权

| 角色 | 来源 | 许可/声明 |
| --- | --- | --- |
| 鲸鱼娘 `card.dsh` | [dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（MIT） | 素材 MIT 许可，已保留上游声明，见 [NOTICE](mods/card.dsh/NOTICE.md) |
| 影 `card.ying` | 非官方同人创作 | 角色 IP 归腾讯及相关权利人；非商业用途，见 [NOTICE](mods/card.ying/NOTICE.md) |

> 请勿将上述角色卡用于商业用途或再分发到第三方平台；引用时保留各自 NOTICE 声明。

### 贡献与隐私

- 欢迎通过 issue / pull request 反馈与贡献；提交前请确保测试全绿。
- 仓库已清理本地绝对路径与工具会话状态文件；提交前请自检，勿带入
  `data/`、`.env`、API 密钥、个人路径或构建产物（`.gitignore` 已配置相应规则）。
