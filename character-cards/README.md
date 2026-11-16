# 角色卡交付包（.chara）

本目录存放从 AnimaPet 内置角色导出的 `.chara` 角色卡压缩包，符合 `chara-1`
格式规范（详见 `docs/chara_format.md`），可直接拖入「模组管理」导入，或用命令行安装：

```bash
python tools/migrate_yingpet.py import-chara character-cards/card.dsh.chara.zip
python tools/migrate_yingpet.py import-chara character-cards/card.ying.chara.zip
```

## 清单

| 文件 | 角色 | 内容 | 素材来源 / 许可 | SHA256 |
| --- | --- | --- | --- | --- |
| `card.dsh.chara.zip` (16 MB) | 鲸鱼娘 | 15 套动画 + 表情/台词/行为 | dsh-pet（MIT，见 NOTICE） | `e7db97f4cfc52bc1cf52fff77df8ed358f3a65615ddf20fd17aecd8b66e851a4` |
| `card.ying.chara.zip` (88 MB) | 影 | 4 套动画 + 8 表情/台词/行为 | 非官方同人（IP 归腾讯，见 NOTICE） | `406285f92636a99b247ad9b09a3d67e7f9e3487b877386942c18ce0a1d25e5fc` |

每个压缩包内含唯一顶层目录（`.chara_stage_<id>/`）与 `manifest.json`（`format=chara-1`），
已通过路径穿越安全检查与导入验证。

## 大文件提示

`card.ying.chara.zip` 约 88 MB，接近 GitHub 单文件 100 MB 上限。若推送时被拒或仓库
体积受限，建议二选一：

1. **不入库**：用 `.gitignore` 忽略 `character-cards/*.zip`，改为在 GitHub Release 中提供下载；
2. **使用 Git LFS**：`git lfs install && git lfs track "character-cards/*.zip"`，再正常提交。

无论哪种方式，角色卡素材的版权声明都以 `mods/card.*/NOTICE.md` 为准。
