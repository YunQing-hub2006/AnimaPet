# AnimaPet 使用指南

面向最终用户: 安装启动、宠物互动、右键菜单、模组管理、设置、角色卡编辑器、
聊天、托盘、日志与数据迁移。

## 1. 安装与启动

### 源码运行

```bash
cd E:\Zcode-work\AnimaPet
run.bat                    # pythonw 无控制台启动(推荐)
.venv\Scripts\python main.py   # 有控制台的调试运行
```

### 打包版(如果已构建)

```text
dist\AnimaPet\AnimaPet.exe    # 双击运行; 目录里必须带 mods\ 和 data\
```

首次运行自动生成 `data/`; 单实例保护, 重复启动会提示“已经在运行”。

## 2. 宠物基础互动

| 操作 | 效果 |
|---|---|
| 左键单击 | 摸头(+好感度, 触发行为规则) |
| 按住拖动 | 移动宠物 |
| 双击 | 打开/关闭聊天窗口 |
| 右键 | 弹出菜单(见下) |

## 3. 右键菜单

```text
摸摸头
表情 ▸    平时/生气/调皮/嘲讽/傲娇/疯批/…
角色卡 ▸  ● 影 (card.ying) / 其他角色…
皮肤 ▸    ● 默认 / 暗色 / 樱
大小 ▸    小 / 中 / 大
久坐提醒: 开/关
功能 ▸    模组管理 / 设置 (API / 人设) / 角色卡管理器… / 聊天窗口 / 其他功能模组
退出
```

## 4. 模组管理

打开: 右键 → 功能 → 模组管理。

- **列表**: 全部模组按类型分组, 行内勾选 = 启用/禁用;
- **新建…**: 导入动画到素材库 / 新建规则模板 / **新建功能模组…**;
- **打开 mods 文件夹 / 导出日志… / 打开日志文件夹**;
- 右键行: 打开所在文件夹 / 导出为模组包 / (皮肤)设为当前 / 删除模组…;
- 顶部: 全部启用 / 全部禁用 / 重新扫描(热重载)。

内置「角色卡管理器」「聊天窗口」也是模组(`feature.charcard` / `feature.chat`),
禁用后对应入口消失, 删除后可放自己的实现替换。

## 5. 设置(API / 人设)

右键 → 功能 → 设置:

- **API Key / Base URL / 模型 / 温度 / 思考强度**: 聊天用(DeepSeek/OpenAI 兼容);
- **当前角色人设**: 直接写回角色卡 `manifest.json`。

> API key 只存在本地 `data/config.json`, 不会上传。

## 6. 角色卡管理器

右键 → 功能 → 角色卡管理器…, 左侧角色列表, 右侧六个页签:

| 页签 | 功能 |
|---|---|
| 人设 | 名称/描述/system_prompt |
| 动画 | 待机/说话动画引用 + PNG 文件夹或 GIF 导入卡内 + 预览 |
| 台词 | 搭话间隔 + 分段台词编辑 |
| 行为 | 可视化规则编辑: 下拉选触发事件、点选动作(说话/表情/动画), 不用写代码; 高级用户可点「编辑选中规则 JSON…」直接改 |
| 表情 | 表情新增/删除/字段(图/动画/时长/台词) |
| 素材库 | 公共动画导入(PNG 文件夹 / GIF)/预览 |

所有保存都先过 `anima.models` 整体校验, 坏数据弹错不落盘。

## 6.1 皮肤工坊

右键 → 功能 → 皮肤工坊…:

- 从默认主题或现有皮肤起步, 点颜色块改配色(窗口/主色/气泡/菜单分组), 中间实时预览;
- 填个 id 和名字点保存 → 生成 `mods/ui.<id>/` 皮肤模组, 与手写皮肤完全同构;
- 默认勾选「保存后立即换上」, 保存即生效; 不满意去「模组管理」删掉重来。

## 7. 聊天窗口

- 打开: 双击宠物 / 右键 → 功能 → 聊天窗口;
- 顶部: 新对话 / 历史 / 当前角色切换 / 备份▾(导出 txt、导出 JSON、从 JSON 恢复) / 清空;
- 第二行: 关键词搜索(回车或点「搜索」, 点「返回」回到当前对话);
- 首次打开(还没有聊天记录)会显示三步上手提示;
- 导入聊天记录: 备份▾ → 从 JSON 恢复, 可选「合并(保留现有, 自动去重)」或「覆盖现有」;
- 需要先配 API key; 缺 key/断网会得到角色内降级回复, 不会崩;
- 历史按角色分目录:`data/characters/<id>/chat_history.json`。

## 8. 系统托盘

- 托盘图标: 角色卡快速切换 / 皮肤快速切换 / 退出;
- 菜单会随模组热重载自动刷新。

## 9. 热重载

- 改 `mods/` 下任何模组文件 → 模组管理「重新扫描」即生效, 无需重启;
- 新增 `.chara` zip → 导入后立刻出现在角色列表;
- 禁用功能模组 = 完整卸载(菜单/事件/状态自动清除), 再启用 = 全新实例。

## 10. 数据文件与备份

| 文件 | 内容 |
|---|---|
| `data/config.json` | API 配置/当前角色/皮肤/启用表 |
| `data/state.json` | 好感度等状态 |
| `data/chat_history/` | 旧/全局聊天历史留档 |
| `data/characters/<id>/chat_history.json` | 各角色聊天历史 |
| `data/pet.log` | 运行日志(可用「导出日志…」备份) |

想复位: 退出应用后备份并删除 `data/config.json`、`data/state.json`。

## 11. 迁移 YingPet 数据

```bash
.venv\Scripts\python tools\migrate_yingpet.py migrate --dry-run      # 先看计划
.venv\Scripts\python tools\migrate_yingpet.py migrate               # 执行(写前备份)
```

已迁移项: config/state/chat_history; 当前角色历史会落到 `data/characters/<id>/`。

## 12. 发布与打包

```bash
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python tools\build_exe.py      # 生成 dist\AnimaPet\
```

发布前真机验证清单: `docs/RELEASE_CHECKLIST.md`。

## 13. 排查问题

1. 右键 → 模组管理: 看有没有 ✗ 加载失败项;
2. 「导出日志…」把 `pet.log` 发出来;
3. 常见: API 没配 key / 模型名写错 / zip 路径含 `..` / 角色卡 `on` 为空。

## 14. 扩展阅读

- 插件开发: `docs/plugin_dev_guide.md`
- .chara 角色卡开发: `docs/chara_dev_guide.md`
- 格式规范: `docs/chara_format.md`
- JSON Schema: `docs/schema/chara.schema.json`