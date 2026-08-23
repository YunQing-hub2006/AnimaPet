# AnimaPet .chara 角色卡格式规范 (chara-1)

> 本文是 Phase 3 的格式规范文档, 与 `docs/schema/chara.schema.json` (生成物, 勿手改)
> 和 `anima/models/character.py` (Pydantic 模型) 同步。改模型后运行
> `python tools/export_chara_schema.py` 重新生成 schema, 测试会断言无漂移。

## 1. 目录结构

一张角色卡是 mods/ 下自包含的文件夹, 物理结构沿用 YingPet card.*:

```text
mods/card.<short>/
├── manifest.json    人设 + 动画引用
├── emotes.json      表情包 (键名 → 表情字段)
├── idle.json        空闲台词包 (分段)
├── behaviors.json   行为规则 (数组)
├── anims/           卡内帧动画
│   └── <短名>/frames/*.png
└── images/          静态表情图
```

`.chara` 包 = 上述文件夹的 zip 打包, 并在 manifest 写入 `"format": "chara-1"` 标记。
旧 `card.*` 卡没有该字段 (空串), 迁移导出时自动补写。

## 2. manifest.json (CardMeta)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string(≥1) | ✅ | 角色卡 id, 规范化 `card.` 前缀 |
| type | string | ✅ | `card` (.chara 包导入时 `chara` 会归一为 `card`) |
| format | string | – | `.chara` 规范标记, 固定 `chara-1`; 旧卡为空 |
| version | string | – | 默认 `1.0.0` |
| name | string | – | 显示名 |
| description | string | – | 一句话描述 |
| system_prompt | string | – | 人设 Prompt (Phase 4 聊天注入) |
| idle_anim | string | – | 待机动画短名/外部引用, 空 = 自动回退 |
| talk_anim | string | – | 说话动画短名/外部引用, 空 = 自动回退 |

未知字段被模型忽略 (extra=ignore), 保存走 `save_card` 只写声明字段;
编辑器/设置界面直接改 `raw` dict 时未知字段原样保留。

## 3. emotes.json (Expression)

```json
{ "emotes": { "default": { "name": "平时", "image": "",
  "anim": "", "hold_ms": 4000, "lines": ["……"] } } }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| 键名 | string | 表情 id (default/tsundere/…) |
| name | string | 显示名 |
| image | string | 静态图相对路径, 空 = 无 |
| anim | string | 动画引用 (卡内短名或 `card.x:short` / `anim.*`) |
| hold_ms | int | 停留毫秒, 默认 4000 |
| lines | string[] | 本地台词, API 不可用时随机用 |

**双名兼容**: Pydantic 聚合视图字段 `expressions` 接受别名 `emotes`;
字典形态 `{"emotes": {id: {...}}}` 与列表形态等价 (模型自动转换)。

## 4. idle.json (IdleLines)

| 字段 | 类型 | 说明 |
|---|---|---|
| interval_min | int | 搭话间隔下限 (秒), 默认 180 |
| interval_max | int | 搭话间隔上限 (秒), 默认 420 |
| lines | dict<string, string[]> | 分段台词 (default/sit/night/petted/…) |

卡内行为规则用 `@idle.this.<段名>` 引用本卡台词包。

## 5. behaviors.json (Behavior)

```json
{ "rules": [ { "on": "pet.petted", "when": "event.affinity % 20 == 0",
  "cooldown": 2, "then": [ { "say": "@idle.this.default" } ] } ] }
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| on | string(≥1) | ✅ | 触发事件 (空 = 永不生效 = 坏数据) |
| when | string | – | 可选条件表达式 |
| cooldown | int(≥0) | – | 冷却秒数, 默认 0 |
| then | object[] | – | 动作 JSON 数组 (say/emote/anim 等) |

模型 `extra=ignore`: 规则里未声明的字段 (如 `if`) 原样透传给规则引擎,
整体校验只拦截 `on` 缺失/类型非法, 不裁剪内容。

## 6. anims/ (Animation)

每个子目录 = 一套帧动画, `frames/*.png` 按文件名排序; 缺少可加载帧时运行时
使用兜底圆盘, 不崩。模型字段: `id` (短名, ≥1), `name`, `fps` (1~60, 默认 12),
`frames_dir` (默认 `frames`)。运行时注册表 id 为 `<卡id>:<短名>`, 归属隔离由
`character` 字段保证。

## 7. id 命名与归一

- 角色卡 id 统一使用 `card.` 前缀 + `[A-Za-z0-9._-]+` 字符集;
- 旧包/其他前缀 (如 `ying.chara`) 在 `packer._normalize_chara_id` 里替换非法字符
  并补 `card.` 前缀;
- `type="chara"` 的 zip 安装时必须回写 `type="card"` + id 归一,
  保证 loader 的 `VALID_TYPES` 与注册表归类一致。

## 8. 校验边界 (两套语义, 有意不同)

- **整体校验** (`anima.models.load_card/save_card`): 编辑器/迁移工具保存把关,
  坏数据抛 `ValueError` 带文件名, 绝不产出半成品包;
- **运行时降级** (`loader._build_card`): 坏表情/规则/台词段丢弃记日志,
  其余照常展开, 扫描绝不因坏子文件崩溃; `_VALIDATE_LIMIT` 防坏数据拖垮扫描。

## 9. zip 打包规范

- 输出带唯一顶层目录 (packer 兼容平铺布局, 但规范导出统一带顶层目录);
- 成员路径拒绝绝对路径/`..` 穿越/盘符 (Zip-Slip 三重防护);
- 过滤 `__pycache__` / `.pyc` / `.tmp`;
- `migrate_yingpet.py export-chara` 先整体校验再打包; `import-chara` 装后
  再整体校验, 失败回滚删除;
- 导入后热重载即可见, 无需重启 (`module_manager.import_zip` / `import_chara`)。