# AnimaPet 插件开发指南

> 面向第三方开发者: 新建功能模组(feature.*)的 Hello World、FeatureContext 白名单 API、
> 两条线程规则、模组结构与热重载约定。

## 1. 最小可用功能模组

在 mods/ 下建一个文件夹(如 mods/feature.hello/), 放两个文件:

```text
mods/feature.hello/
├── manifest.json
└── plugin.py
```

manifest.json:

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

plugin.py:

```python
class Feature:
    id = "feature.hello"
    name = "你好"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("打个招呼", self._hello)
        ctx.on("timer.idle", lambda _p: self.ctx.log("idle tick"))

    def _hello(self):
        self.ctx.say("你好, 我是功能模组。")

    def on_disable(self):
        pass   # 停线程/计时器在这里做
```

保存后在「模组管理 → 重新扫描」即生效(热重载), 无需重启。

## 2. FeatureContext 白名单 API

| API | 用途 |
|---|---|
| `ctx.emit(name, payload)` | 发事件, 可被行为规则监听 |
| `ctx.on(name, fn)` | 订阅事件, 插件卸载自动退订 |
| `ctx.say(text, hold_ms=0)` | 宠物气泡说话 |
| `ctx.emote(emote_id, after_ms=0)` | 宠物做表情 |
| `ctx.add_menu_action(label, callback)` | 右键菜单追加一项 |
| `ctx.get_state(key=None)` / `ctx.set_state(key, value)` | 持久化状态(state.json) |
| `ctx.log(msg)` | 日志 |
| `ctx.data` | 跨热重载的插件私有数据字典 |
| `ctx.registry` / `ctx.config` / `ctx.save_config()` | 只读注册表/全局配置 |
| `ctx.reload()` | 热重载全部模组 |
| `ctx.register_action(name, fn)` | 注册自定义行为动作 |
| `ctx.pet` | 宠物窗口(仅作 parent/几何; 表现请用 say/emote) |
| `ctx.open_path(path)` | 系统默认方式打开路径 |

插件只应使用上表白名单, 不要 import anima 内部模块(那是官方插件的地盘)。

## 3. 两条线程规则(TD1-A)

1. **QWidget 只能在 Qt 主线程创建/访问**。插件 `on_load` 运行在内核 asyncio 线程,
   若需要窗口/对话框, 必须经 `ctx...` 机制或官方 `bridge.run_on_ui` 封送到主线程;
2. **阻塞 IO 不要卡内核线程**。官方 LLM 适配器把 sync requests 包进
   `asyncio.to_thread`; 功能模组如需网络, 用 `asyncio.to_thread` 或
   `QtCore.QThread`(不要直接在内核线程里 requests)。

## 4. 模组类型速查

| type | 内容 | 说明 |
|---|---|---|
| card | 角色卡 | 自包含人设/动画/台词/行为/表情 |
| behavior | 规则 | `rules: [{on, when, cooldown, then}]` |
| anim | 帧动画 | `frames/*.png` |
| emote | 表情 | 单表情或 `emotes` 字典包 |
| idle | 台词包 | `lines: {段名: [台词]}` |
| ui | 皮肤 | `theme: {配色覆盖}` |
| feature | 功能插件 | 本指南的 plugin.py |

## 5. 打包与安装

- 任意模组文件夹可打包为 zip(顶层目录 = 文件夹名), 拖入/菜单导入即装;
- Zip-Slip 防护: 拒绝绝对路径/`..` 穿越/盘符; 过滤 __pycache__/.pyc;
- `.chara` 角色卡包是 card.* 文件夹 + `manifest.format="chara-1"`, 导入自动归一 id;
- 角色卡 JSON Schema 见 docs/schema/chara.schema.json, 规范见 docs/chara_format.md。

## 6. 一键脚手架

```bash
.venv\Scripts\python tools\new_plugin.py greet 问候
```

会在 mods/feature.greet/ 生成 manifest.json + plugin.py, 并在模组管理里重新扫描后生效。

## 7. 常见坑

- 菜单/事件/状态在禁用(完整卸载)后自动清理, 不要在手势回调里直接访问已卸载服务;
- `ctx.data` 跨热重载保留, 但禁用再启用会换新实例(数据仍在, 实例引用会变);
- 不要在 plugin.py 顶层做耗时/网络工作(会在导入时执行)。