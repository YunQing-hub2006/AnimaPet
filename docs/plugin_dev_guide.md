# AnimaPet 插件开发指南

本文面向第三方开发者, 说明如何在 AnimaPet 里写一个**功能模组(feature.*)**:

- 最小 Hello World 与生命周期
- `FeatureContext` 白名单 API(菜单/事件/状态/UI/异步/服务)
- 两条线程规则
- 调试、热重载、打包与替换内置功能

内置的「角色卡管理器」「聊天窗口」本身就是这种模组(`mods/feature.charcard/`、
`mods/feature.chat/`), 你可以删除它们或用自己的实现替换。

## 1. 两种插件形态

| 形态 | 位置 | 契约 | 给谁用 |
|---|---|---|---|
| 功能模组 | `mods/feature.*/` | `class Feature` + `FeatureContext` | 第三方/用户 |
| 官方插件 | `anima/plugins/*.py` | `anima.core.Plugin` + `Context` | 框架基础设施 |

**普通开发只需要功能模组**, 不要改 `anima/`(那是框架地盘)。

## 2. 最小可用功能模组

在 `mods/` 下建文件夹(如 `mods/feature.hello/`), 放两个文件:

```text
mods/feature.hello/
├── manifest.json
└── plugin.py
```

`manifest.json`(模组声明):

```json
{
  "id": "feature.hello",
  "type": "feature",
  "version": "1.0.0",
  "name": "你好",
  "main": "plugin.py",
  "description": "示例功能模组"
}
```

`plugin.py`(必须定义 `Feature` 类):

```python
class Feature:
    id = "feature.hello"
    name = "你好"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("打个招呼", self._hello)
        ctx.on("character.switched", lambda _p: self.ctx.log("角色切了"))

    def _hello(self):
        self.ctx.say("你好, 我是功能模组。")

    def on_disable(self):
        pass   # 停线程/计时器在这里做
```

保存后打开「模组管理 → 重新扫描」即生效(热重载), 无需重启。

## 3. FeatureContext 白名单 API

| API | 用途 |
|---|---|
| `ctx.emit(name, payload)` | 发事件(可被行为规则监听) |
| `ctx.on(name, fn)` | 订阅事件(插件卸载自动退订) |
| `ctx.say(text, hold_ms=0)` | 宠物气泡说话 |
| `ctx.emote(emote_id, after_ms=0)` | 宠物做表情 |
| `ctx.add_menu_action(label, callback)` | 右键菜单追加一项 |
| `ctx.get_state(key=None)` / `ctx.set_state(key, value)` | 持久化状态(state.json) |
| `ctx.data` | 跨热重载的插件私有数据字典 |
| `ctx.task(coro)` | 把异步任务调度到内核循环(跨线程安全) |
| `ctx.run_on_ui(fn, *args)` | 在 Qt 主线程执行 fn(动 UI 必须用) |
| `ctx.use("服务名")` | 获取官方服务(bridge/character_manager/...) |
| `ctx.registry` | 只读模组注册表 |
| `ctx.config` / `ctx.save_config()` | 全局配置 dict/保存 |
| `ctx.log(msg)` | 日志 |
| `ctx.reload()` | 热重载全部模组 |
| `ctx.register_action(name, fn)` | 注册自定义行为动作 |
| `ctx.pet` | 宠物窗口(仅作 parent/取几何; 表现请用 say/emote) |
| `ctx.open_path(path)` | 系统默认方式打开路径 |

## 4. 两条线程规则(TD1-A)

1. **QWidget 只能在 Qt 主线程创建/访问**。
   - `on_load` 运行在内核 asyncio 线程, 不要直接 `QWidget()`;
   - 用 `ctx.run_on_ui(lambda: 创建/操作控件)` 封送;
2. **阻塞 IO 不要卡内核线程**。
   - 网络请求用 `asyncio.to_thread`(参考 `anima/adapters/openai_compat.py`);
   - 或交给 Qt `QThread`, 但回调 UI 仍需 `ctx.run_on_ui`。

### UI + 异步示例(聊天式功能模组的骨架)

```python
class Feature:
    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("我的窗口", self._open)

    def _open(self):
        self.ctx.run_on_ui(self._build_dialog)

    def _build_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self.ctx.pet, "你好", "我是 Qt 主线程")

    async def _network(self):
        import asyncio, requests
        def do():
            return requests.get("https://example.com").status_code
        code = await asyncio.to_thread(do)   # 不卡内核线程
        self.ctx.run_on_ui(lambda: self.ctx.log("status=" + str(code)))
```

## 5. 常用事件名

| 事件 | 触发时机 | payload |
|---|---|---|
| `pet.petted` | 左键摸头 | `{"affinity": n}` |
| `pet.double_clicked` | 双击宠物 | `{}` |
| `pet.drag_started/ended` | 拖拽开始/结束 | `{}` |
| `character.switch` | 请求切换角色 | `{"character": id}` |
| `character.switched` | 切换完成 | `{"character": id}` |
| `mods.reloaded` | 模组重扫 | `{"errors": [...]}` |
| `ui.changed` | 皮肤切换 | `{"ui": id}` |
| `state.changed` | 状态变化 | `{"key", "value"}` |
| `chat.send` / `chat.reply` | 聊天收发 | 见代码 |

完整表见 `anima/events.py`。

## 6. 模组类型速查

| type | 内容 | 说明 |
|---|---|---|
| card | 角色卡 | 自包含人设/动画/台词/行为/表情 |
| behavior | 规则 | `rules: [{on, when, cooldown, then}]` |
| anim | 帧动画 | `frames/*.png` |
| emote | 表情 | 单表情或 `emotes` 字典包 |
| idle | 台词包 | `lines: {段名: [台词]}` |
| ui | 皮肤 | `theme: {配色覆盖}` |
| feature | 功能插件 | 本指南 |

## 7. 调试与日志

- `ctx.log("消息")` 写入 `data/pet.log`;
- 模组加载失败会在「模组管理」中显示为 ✗ 错误项;
- 「导出日志…」可把 `pet.log` 复制出来给开发者排查;
- 不要在 `plugin.py` **顶层**做耗时/网络工作(模块导入时执行)。

## 8. 热重载 / 打包 / 替换内置

- **热重载**: 改完文件 → 模组管理 → 重新扫描(无需重启);
- **导入/导出**: 模组管理右键行可导出 zip; 拖入 zip 或「导入」即可安装;
- **脚手架**:
  ```bash
  .venv\Scripts\python tools\new_plugin.py greet 问候
  ```
  或在「模组管理 → 新建… → 新建功能模组…」创建;
- **替换内置**: 删掉 `mods/feature.chat/`、`mods/feature.charcard/`, 再放你自己的同 id 模组;
- **禁用**: 模组管理里取消勾选 → 完整卸载(菜单/事件/状态自动清理); 再启用 = 全新实例。

## 9. 常见坑

- α: 在 `on_load` 里直接创建 QWidget → 线程错误; 用 `ctx.run_on_ui`;
- β: 在 UI 回调里 `asyncio.ensure_future` → 无运行循环; 用 `ctx.task(coro)`;
- γ: 用 `ctx.config.get("mods.character")` → 这是 dict, 请用 `ctx.config["mods"]["character"]`;
- δ: 禁用后再访问旧 `ctx.data` 的窗口引用 → 实例已卸载, 先判 None。