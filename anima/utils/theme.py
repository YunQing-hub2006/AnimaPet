# -*- coding: utf-8 -*-
"""主题: 默认配色 + 皮肤合并。

皮肤模组(ui.*)的 theme 字典按同名键覆盖默认值;
皮肤数据不可信, 只允许覆盖字符串配色项。
"""

DEFAULT_THEME = {
    "font_family": "Microsoft YaHei",
    "font_size": 10,
    "bg_window": "#241a30",     # 窗口底色
    "bg_panel": "#241a30",      # 输入框/下拉框底色
    "fg_panel": "#f0e6ff",      # 输入框/下拉框文字
    "bg_browser": "#1d1526",    # 聊天区底色
    "fg_browser": "#f0e6ff",    # 聊天区文字
    "accent": "#b04060",        # 主色(边框/名字/发送按钮)
    "accent_hover": "#d05070",
    "btn_bg": "#3a2a4a",        # 工具条按钮底色
    "btn_fg": "#f0e6ff",
    "status_fg": "#a08cb0",     # 状态栏/系统提示文字
    "user_bubble_bg": "#5a2a40",   # 用户气泡底色
    "user_bubble_fg": "#ffdce8",
    "pet_bubble_bg": "#2c2138",    # 宠物气泡底色
    "pet_bubble_fg": "#f0e6ff",
    "bubble_bg": "rgba(30, 20, 40, 220)",  # 桌宠头顶气泡底色
    "bubble_fg": "#f0e6ff",                # 桌宠头顶气泡文字
    "menu_bg": "#241a30",                  # 右键菜单底色
    "menu_fg": "#f0e6ff",                  # 右键菜单文字
    "menu_hover": "#b04060",               # 右键菜单选中项底色
    "qss": "",                  # 可选: 整段追加的 QSS
}


def merge_theme(theme):
    """默认主题 + 皮肤主题浅合并, 非字符串键忽略(皮肤模组不可信, 只许覆盖配色)。"""
    t = dict(DEFAULT_THEME)
    for k, v in (theme or {}).items():
        if k in t and isinstance(v, str) and v.strip():
            t[k] = v.strip()
    try:
        t["font_size"] = int(t["font_size"])
    except (TypeError, ValueError):
        t["font_size"] = DEFAULT_THEME["font_size"]
    return t
