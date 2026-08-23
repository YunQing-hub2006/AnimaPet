# AnimaPet .chara 角色卡开发指南

本文教你如何**开发/制作一张角色卡**: 从零建卡、写人设、做动画、配表情、
写行为规则, 最后导出/打包成 `.chara` 分享。格式细节见 `docs/chara_format.md`,
JSON Schema 见 `docs/schema/chara.schema.json`(自动生成, 勿手改)。

## 1. 概念

- **角色卡文件夹**(`mods/card.xxx/`): 一张自包含角色;
- **.chara**: 角色卡文件夹打包成的 zip, `manifest.format = "chara-1"`;
- 运行时**逐文件降级**: 某个文件坏了只丢坏项, 角色照常加载;
- 编辑器/工具保存走**整体校验**: 坏数据明确报错, 不落盘。

## 2. 快速创建方式

| 方式 | 适合 |
|---|---|
| 角色卡管理器 →「新建角色卡…」向导 | 最推荐, 自动生成完整骨架 |
| 手动建 `mods/card.xxx/` + 4 个 JSON | 你会手写/脚本生成 |
| 从 YingPet card.* 复制后补 `format` 字段 | 迁移已有角色 |
| `tools/migrate_yingpet.py export-chara card.xxx --out out.chara.zip` | 规范化导出 |

## 3. 目录结构

```text
mods/card.ying/
├── manifest.json      人设 + 动画引用
├── emotes.json        表情包
├── idle.json          空闲台词包
├── behaviors.json     行为规则
├── anims/
│   ├── idle/frames/*.png
│   └── talk/frames/*.png
└── images/            静态表情图(可选)
```

## 4. manifest.json

```json
{
  "id": "card.ying",
  "type": "card",
  "format": "chara-1",
  "version": "1.0.0",
  "name": "影",
  "description": "一句话描述",
  "system_prompt": "你是…(人设 Prompt, 聊天时注入)",
  "idle_anim": "idle",
  "talk_anim": "talk"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| id | ✅ | `card.` 前缀 + 小写字母/数字/_.- |
| type | ✅ | `card`(`.chara` 导入时 `chara` 自动归一为 `card`) |
| format | – | `.chara` 规范标记, 固定 `chara-1` |
| name | – | 显示名 |
| description | – | 描述 |
| system_prompt | – | 人设 Prompt |
| idle_anim / talk_anim | – | 卡内短名或外部 id; 空 = 自动回退 |

## 5. emotes.json(表情)

```json
{
  "emotes": {
    "default": { "name": "平时", "image": "", "anim": "", "hold_ms": 4000,
                  "lines": ["……"] },
    "angry":   { "name": "生气", "anim": "card.ying:angry", "hold_ms": 5000,
                  "lines": ["啧, 别烦我。"] }
  }
}
```

- 键名 = 表情 id(必须包含一个 `default`);
- `image`: 静态图相对路径; `anim`: 动画引用;
- `hold_ms`: 停留毫秒; `lines`: 本地台词(API 不可用时随机用);
- 模型层 `expressions` 与 `emotes` 双名兼容, 编辑器/迁移工具都能读。

## 6. idle.json(空闲台词)

```json
{
  "interval_min": 180,
  "interval_max": 420,
  "lines": { "default": ["云梦泽多么有趣"], "petted": ["别摸头。"] }
}
```

- 段名可自定义: `default/sit/night/petted/lifted/...`;
- 行为规则用 `@idle.this.<段名>` 引用本卡台词。

## 7. behaviors.json(行为规则)

```json
{
  "rules": [
    {
      "on": "pet.petted",
      "when": "event.affinity % 20 == 0",
      "cooldown": 2,
      "then": [{"say": "……好感度 {event.affinity}"}, {"emote": "tsundere"}]
    }
  ]
}
```

- `on` 必填且非空(空 = 永不生效 = 坏数据);
- `when`: 可选条件表达式; `cooldown`: 秒;
- `then`: 动作数组, 内置动作 `say`/`emote`/`anim`, 也支持 `ctx.register_action` 自定义;
- 未声明字段(如 `if`)会原样传给规则引擎, 不会被模型裁剪。

### 动作/模板速查

| 写法 | 效果 |
|---|---|
| `"say": "@idle.this.petted"` | 说本卡台词包 petted 段 |
| `"say": "好感度 {event.affinity}"` | 模板插值 |
| `"emote": "angry"` | 做表情 |
| `"anim": "card.ying:talk"` | 播动画 |

## 8. anims/(帧动画)

- `anims/<短名>/frames/*.png`, 文件名排序即帧序;
- 没有有效 PNG 时运行时用兜底圆盘, 不会崩;
- 卡内短名引用: manifest 写 `idle`/`talk`; 外部引用写全 id(`anim.x` / `card.y:z`);
- 表情也可以引用卡内动画: `"anim": "card.ying:angry"`。

## 9. 多角色与上下文隔离

- 卡内素材挂 `card.<id>:` 命名空间, 自动按角色隔离;
- 聊天历史落 `data/characters/<id>/chat_history.json`;
- 行为规则按 `character` 字段只在本角色激活时触发。

## 10. 校验与常见错误

| 错误 | 原因 | 解决 |
|---|---|---|
| 缺 manifest | 不是角色卡文件夹 | 建 manifest.json |
| manifest 缺 id | 没写 id | 补 `id` |
| `Behavior.on` 空 | 规则无触发事件 | 填 `on` |
| 动画帧 0 张 | frames 没 PNG | 放 png 或先不引用(回退) |
| 导入后未知类型 chara | 旧包类型没归一 | 用 `import-chara`/`import_zip` 导入 |

## 11. 导出/导入/分享

```bash
# 导出规范化 .chara(整体校验 + format=chara-1)
.venv\Scripts\python tools\migrate_yingpet.py export-chara card.ying --out E:\ying.chara.zip

# 安装(装后整体校验, 失败回滚; --activate 设为当前角色)
.venv\Scripts\python tools\migrate_yingpet.py import-chara E:\mio.chara.zip --activate
```

也可以在「模组管理」里右键导出/拖入导入。

## 12. 参考

- 格式规范(字段权威): `docs/chara_format.md`
- JSON Schema: `docs/schema/chara.schema.json`
- 真实示例: `mods/card.ying/`(含 8 表情/多段台词/行为规则/卡内动画)
- Schema 生成器: `tools/export_chara_schema.py`(改模型后重新生成)