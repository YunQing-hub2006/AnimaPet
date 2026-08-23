# AnimaPet v1.0 真机冒烟清单

> 用于用户环境验证(源码 run.bat 或 dist/AnimaPet/AnimaPet.exe)。
> 自动化已覆盖: pytest 254 passed, benchmark 启动 1.520s / 峰值 6.5 MiB (offscreen)。

## 1. 启动

- [ ] `run.bat` 或 `dist\AnimaPet\AnimaPet.exe` 启动后右下角出现宠物
- [ ] 无闪退/无“已存在实例”误报
- [ ] `data\pet.log` 有启动日志

## 2. 右键菜单与托盘

- [ ] 右键菜单包含: 模组管理 / 设置 (API / 人设) / 角色卡管理器… / 聊天窗口
- [ ] 托盘图标显示; 托盘可切换角色/皮肤/退出

## 3. 角色卡 / .chara

- [ ] 角色卡管理器 6 页签打开正常(人设/动画/台词/行为/表情/素材库)
- [ ] 改人设 → 保存 → 宠物/设置立即反映(热重载)
- [ ] 新建角色卡向导生成自包含 card.* 并自动切换
- [ ] 拖入/导入 .chara zip 后无需重启即可见
- [ ] 坏 manifest 有明确错误且应用不崩

## 4. 聊天与多 LLM

- [ ] 设置里配 API key/base_url/model
- [ ] 聊天窗发送后收到角色回复, 气泡说话
- [ ] 模型返回 emotion 时宠物表情切换
- [ ] 切换角色后聊天历史按角色隔离
- [ ] 导出 txt/JSON、导入 JSON 正常
- [ ] 缺 key/断网得到角色内降级回复(不崩)

## 5. 一切皆插件(方案 A)

- [ ] 模组管理里能看到「角色卡管理器」「聊天窗口」(feature.charcard / feature.chat)
- [ ] 禁用 feature.chat → 菜单入口消失, 不再请求 API; 再启用恢复
- [ ] 禁用 feature.charcard → 角色卡入口消失; 再启用恢复
- [ ] 「新建… → 新建功能模组…」能生成模板并出现在列表

## 6. 日志与排查

- [ ] 模组管理「导出日志…」导出 pet.log 副本
- [ ] 「打开日志文件夹」打开 data/ 目录

## 7. 打包产物

- [ ] `dist\AnimaPet\AnimaPet.exe` 单独拷贝到别的目录后能启动
- [ ] 打包目录带上 `mods\`(含 feature.chat/feature.charcard)

## 8. 收尾

- [ ] 全部通过后删除 `E:\Zcode-work\Anima-core-old\core` 归档
- [ ] 如需正式发布再补 PyInstaller 图标/单文件版/签名