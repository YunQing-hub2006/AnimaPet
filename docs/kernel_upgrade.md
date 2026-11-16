# 内核更换说明

## 背景

- 上游内核（修复版）：`Anima-v1.1\anima\core`
- 桌面宠物内嵌内核（旧版）：`AnimaPet\anima\core`
- 旧内核归档：`<本地归档目录>/core`（替换下来的老内核，回滚用）
- 两者不同文件：`app.py`、`bus.py`、`context.py`、`lifecycle.py`、`__init__.py`

> 说明：`AnimaPet/anima/core` 是内嵌副本，更新时以 `Anima-v1.1` 为准。

## 更换步骤

```bash
# 1. 备份当前内嵌内核（防出问题可回滚）
cp -r "AnimaPet\anima\core" "AnimaPet\anima\core.bak"

# 2. 删除旧内核
rm -rf "AnimaPet\anima\core"

# 3. 复制新内核（只复制 .py 源码，pyc 缓存不要带）
cp -r "Anima-v1.1\anima\core" "AnimaPet\anima\core"
find "AnimaPet\anima\core" -name "__pycache__" -type d -exec rm -rf {} +

# 4. 验证内核可正常导入
python -c "from anima.core import app; print('kernel OK')"
```

## 验证

- 运行桌面宠物：`AnimaPet\run.bat`
- 确认修复的 bug 已生效，且原有功能正常（插件、模组、窗口）

## 注意事项

1. **只替换 `anima\core` 目录**，`plugins`、`mods`、`utils`、`window` 不要动。
2. 新内核来自 `Anima-v1.1`，若该目录后续有更新，重复以上步骤即可。
3. 旧内核已归档至 `<本地归档目录>/core`，确认新版运行正常后该归档可删除。
4. 若更换后出现问题，用归档的旧内核还原即可：
   ```bash
   rm -rf "AnimaPet\anima\core"
   mv "<本地归档目录>/core" "AnimaPet\anima\core"
   ```


## v1.3.0 更换记录（本次）

- 内嵌内核 **v1.1.1 -> v1.3.0**：覆盖 `anima/core/*.py` 共 10 个文件（新增 `log.py`）。
- **必改项**：`anima/plugins/feature_host.py` 里 `FeatureAdapter.ctx` 原本是
  **只读 property**，而 v1.2+ 内核会在 `load()` 之前注入 `plugin.ctx = ctx`，
  只读属性会直接抛 `AttributeError`（表现：**所有 feature 模组装载失败**）。
  已给它补上 setter。
  → 结论：`ctx` 是内核**保留属性名**，插件子类不要再声明自己的只读 `ctx`。
- **测试同步**：`tests/test_core/test_plugin.py` 两处 `dependencies == []`
  改为 `== ()`（v1.1.2 起默认值是不可变元组，不再共享同一个 list）。
- **验证**：`pytest tests/` **268 passed**，含 offscreen Qt 全链路集成测试
  （真实 52 个模组走 `FeatureAdapter`），即上面那个坑已被端到端覆盖。
- **回滚副本**：`<本地归档目录>/core-animapet-v1.1.1`
  （刻意放在仓库外：放 `anima/core.bak` 虽然按本文档老步骤可行，但会被
  `git add -A` 误提交，而且 `anima*` 的打包扫描会看到这个目录）。
- **遗留**：`tests/test_core/` 是 v1.1.1 的**裁剪副本**（缺 v1.1.1 的批量原子性
  与顺序契约测试，也没有 v1.1.2~v1.3.0 的新测试）。要与上游一致就从
  `Anima-v1.1\tests\test_core` 同步，但要排除
  `test_examples.py`（它依赖上游的 `examples/` 目录）。

> 补充：内嵌内核随后已跟到 **v1.3.1**（`ctx` 明确为保留属性名 + 注入失败
> 改抛带说明的 `LifecycleError`，并收紧了若干冗余 docstring）。该版本无行为影响，
> `tests/test_core/` 也已同步，AnimaPet 全量测试 **346 passed**。
