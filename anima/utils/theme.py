# -*- coding: utf-8 -*-
"""主题设计系统: 默认配色 + 皮肤合并 + 组件 QSS 工厂。

三层结构:
    DEFAULT_THEME  唯一的颜色/字体取值来源(皮肤模组可按键覆盖);
    merge_theme()  默认 + 皮肤浅合并(皮肤不可信, 只允许覆盖字符串配色项);
    menu_qss()/dialog_qss()  用合并后的主题生成整段 QSS, 各窗口统一套用。

以前各对话框各自维护一份白色 QSS, 与主界面的深紫配色割裂; 现在所有窗口
都从同一份主题取色, 皮肤模组热重载后全局一致生效。

关于"推导色"
------------
皮肤模组通常只覆盖 14 个主色键(见 mods/ui.*/manifest.json), 而菜单/气泡/
边框/悬停态这些衍生色几乎没人写。若一律回退硬编码默认值, 浅色皮肤就会顶着
深色右键菜单(ui.sakura 正是如此)。因此 merge_theme 会用 _shade() 按同色系
推导缺失的衍生键 —— 皮肤显式写了就听皮肤的, 没写就跟主色走。
"""
from __future__ import annotations

DEFAULT_THEME = {
    "font_family": "Microsoft YaHei",
    "font_size": 10,

    # 层次: browser(聊天区) 最暗 -> window(底色) -> panel(输入) -> elevated(浮层)
    "bg_window": "#241a30",
    "bg_panel": "#2b2039",
    "fg_panel": "#f0e6ff",
    "bg_elevated": "#342545",
    "bg_browser": "#1d1526",
    "fg_browser": "#ece2f7",

    "border": "#46335e",           # 常态描边(弱)
    "border_strong": "#6a4c8d",    # 悬停/分隔(强)

    "accent": "#bf4a68",           # 主色: 边框激活/名字/发送
    "accent_hover": "#d66484",
    "accent_pressed": "#953a51",
    "accent_soft": "#46253c",      # 主色淡底(选中项/复选框)

    "btn_bg": "#352843",
    "btn_fg": "#ece2f7",
    "btn_hover": "#56416c",

    "status_fg": "#9d8bb0",        # 状态栏/系统提示(次要文字)

    "user_bubble_bg": "#6b2f47",   # 聊天: 用户气泡
    "user_bubble_fg": "#ffdce8",
    "pet_bubble_bg": "#2f2440",    # 聊天: 宠物气泡
    "pet_bubble_fg": "#ece2f7",

    "bubble_bg": "rgba(36, 26, 48, 230)",  # 桌宠头顶气泡(半透明浮在桌面上)
    "bubble_fg": "#ece2f7",
    "menu_bg": "#342545",                  # 右键菜单底色
    "menu_fg": "#ece2f7",
    "menu_hover": "#bf4a68",
    "qss": "",                     # 可选: 整段追加的 QSS
}
# 注: 带"推导"性质的键(border/btn_hover/menu_bg/bubble_bg 等)的取值就是
# _derive() 对上面这组主色的计算结果 —— 两者必须一致, 否则 DEFAULT_THEME
# 里会躺着永远用不到的死值(见 tests/test_utils.py::test_theme_merge_none_safe)。

def _clamp(v):
    return max(0, min(255, int(round(v))))


def _rgb(color):
    """#rrggbb -> (r, g, b); 非 hex 或解析失败返回 None。"""
    c = (color or "").strip()
    if len(c) == 7 and c.startswith("#"):
        try:
            return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        except ValueError:
            return None
    return None


def _hex(r, g, b):
    return "#%02x%02x%02x" % (_clamp(r), _clamp(g), _clamp(b))


def _lighten(color, amount):
    """保色相地提亮: 往"本色调到最亮"的版本插值。

    直接往白插值会把深紫 #241a30 洗成灰 #87818d(失去色相); 往本色的最亮
    版本插值则保住紫调。无彩色(纯灰/黑)的最亮版本恰好就是白, 于是自动退化
    成往白插值 —— 深色皮肤 #141414 仍能拿到看得见的 #484848 描边。
    """
    rgb = _rgb(color)
    if rgb is None:
        return color
    r, g, b = rgb
    mx = max(r, g, b)
    if mx <= 0:
        v = 255 * amount
        return _hex(v, v, v)
    k = 255.0 / mx
    return _hex(r + (r * k - r) * amount,
                g + (g * k - g) * amount,
                b + (b * k - b) * amount)


def _shade(color, amount):
    """hex 颜色提亮(amount>0)或压暗(amount<0), amount 是 -1~1 的比例。"""
    rgb = _rgb(color)
    if rgb is None:
        return color
    if amount >= 0:
        return _lighten(color, amount)
    r, g, b = rgb
    k = 1 + amount
    return _hex(r * k, g * k, b * k)


def _contrast_shade(color, amount):
    """按底色明暗自动选方向的 shade: 深底提亮、浅底压暗。

    一律"提亮"在浅色皮肤上会算出看不见的白边框(ui.sakura 的白底
    需要压暗才拉得开层次), 所以这里先看亮度再决定方向。
    """
    rgb = _rgb(color)
    if rgb is None:
        return color
    lum = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0
    return _shade(color, -amount if lum > 0.6 else amount)


def _mix(c1, c2, w2):
    """两色混合, w2 是 c2 的占比(0~1)。用于"主色淡底"这类需要
    跟着底色走的色: 单纯压暗在浅色皮肤上会得到脏脏的深色。"""
    a, b = _rgb(c1), _rgb(c2)
    if a is None or b is None:
        return c1
    return _hex(a[0] + (b[0] - a[0]) * w2,
                a[1] + (b[1] - a[1]) * w2,
                a[2] + (b[2] - a[2]) * w2)


def _translucent(color, alpha):
    """hex -> rgba(...,alpha); 给头顶气泡用(要透出桌面)。"""
    c = (color or "").strip()
    if len(c) == 7 and c.startswith("#"):
        try:
            return "rgba(%d, %d, %d, %d)" % (int(c[1:3], 16), int(c[3:5], 16),
                                             int(c[5:7], 16), int(alpha))
        except ValueError:
            return c
    return c


def _derive(skin, t):
    """补齐皮肤没写的衍生色(见模块文档"关于推导色")。

    皮肤显式写了的键一律不动 —— 只对缺失项做同色系推导。
    """
    def missing(key):
        return not str(skin.get(key, "") or "").strip()

    # 浮层统一一档高度色: 菜单/下拉/悬停用同一个, 免得浅色皮肤下
    # 出现"比底色还深"的怪浮层
    if missing("bg_elevated"):
        t["bg_elevated"] = _contrast_shade(t["bg_window"], 0.10)
    if missing("border"):
        t["border"] = _contrast_shade(t["bg_window"], 0.22)
    if missing("border_strong"):
        t["border_strong"] = _contrast_shade(t["bg_window"], 0.45)
    if missing("btn_hover"):
        t["btn_hover"] = _contrast_shade(t["btn_bg"], 0.22)
    if missing("menu_bg"):
        t["menu_bg"] = t["bg_elevated"]
    if missing("menu_fg"):
        t["menu_fg"] = t["fg_browser"]
    if missing("menu_hover"):
        t["menu_hover"] = t["accent"]
    if missing("bubble_fg"):
        t["bubble_fg"] = t["fg_browser"]
    if missing("accent_soft"):
        t["accent_soft"] = _mix(t["accent"], t["bg_window"], 0.78)
    if missing("accent_pressed"):
        t["accent_pressed"] = _shade(t["accent"], -0.22)
    if missing("bubble_bg"):
        t["bubble_bg"] = _translucent(t["bg_window"], 230)


def merge_theme(theme):
    """默认主题 + 皮肤主题浅合并, 非字符串键忽略(皮肤模组不可信, 只许覆盖配色)。"""
    t = dict(DEFAULT_THEME)
    skin = theme or {}
    for k, v in skin.items():
        if k in t and isinstance(v, str) and v.strip():
            t[k] = v.strip()

    _derive(skin, t)

    try:
        t["font_size"] = int(t["font_size"])
    except (TypeError, ValueError):
        t["font_size"] = DEFAULT_THEME["font_size"]
    return t


# 圆角基准(像素)。皮肤只换配色, 不动这些, 保证布局稳定。
RADIUS = 10       # 面板/菜单
RADIUS_SM = 7     # 按钮/输入框
RADIUS_LG = 14    # 气泡


def menu_qss(t):
    """右键菜单 / 托盘菜单样式。"""
    return (
        "QMenu { background: %(menu_bg)s; color: %(menu_fg)s;"
        " border: 1px solid %(border_strong)s; border-radius: %(r)ipx;"
        " padding: 5px; }"
        "QMenu::item { padding: 6px 24px 6px 12px; border-radius: %(rs)ipx;"
        " margin: 1px 2px; }"
        "QMenu::item:selected { background: %(menu_hover)s; color: #ffffff; }"
        "QMenu::item:disabled { color: %(status_fg)s; }"
        "QMenu::separator { height: 1px; background: %(border)s;"
        " margin: 5px 10px; }"
        "QMenu::indicator { width: 14px; height: 14px; left: 6px; }"
    ) % dict(t, r=RADIUS, rs=RADIUS_SM)


_DIALOG_QSS_TEMPLATE = """
QDialog, QWidget { background: %(bg_window)s; color: %(fg_browser)s;
 font-family: '%(font_family)s'; font-size: %(font_size)spt; }
QLabel { background: transparent; color: %(fg_browser)s; }

QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox, QDoubleSpinBox {
 background: %(bg_panel)s; color: %(fg_panel)s;
 border: 1px solid %(border)s; border-radius: %(rs)ipx; padding: 6px 8px;
 selection-background-color: %(accent)s; selection-color: #ffffff; }
QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus,
QComboBox:focus, QSpinBox:focus {
 border: 1px solid %(accent)s; background: %(bg_elevated)s; }
QLineEdit:disabled, QPlainTextEdit:disabled { color: %(status_fg)s; }

QListWidget, QTreeWidget { background: %(bg_browser)s; color: %(fg_browser)s;
 border: 1px solid %(border)s; border-radius: %(r)ipx; padding: 3px; }
QListWidget::item, QTreeWidget::item { padding: 5px 6px; border-radius: %(rs)ipx; }
QListWidget::item:hover, QTreeWidget::item:hover { background: %(bg_elevated)s; }
QListWidget::item:selected, QTreeWidget::item:selected {
 background: %(accent)s; color: #ffffff; }

QPushButton { background: %(btn_bg)s; color: %(btn_fg)s;
 border: 1px solid %(border)s; border-radius: %(rs)ipx;
 padding: 6px 14px; }
QPushButton:hover { background: %(btn_hover)s; border-color: %(border_strong)s; }
QPushButton:pressed { background: %(accent_pressed)s; color: #ffffff;
 border-color: %(accent_pressed)s; }
QPushButton:disabled { color: %(status_fg)s; background: %(bg_panel)s;
 border-color: %(border)s; }
QPushButton:checked { background: %(accent)s; color: #ffffff;
 border-color: %(accent)s; }
QDialogButtonBox QPushButton { min-width: 84px; }

QCheckBox, QRadioButton { background: transparent; color: %(fg_browser)s;
 spacing: 6px; }
QCheckBox::indicator, QRadioButton::indicator {
 width: 15px; height: 15px; border: 1px solid %(border_strong)s;
 border-radius: 4px; background: %(bg_panel)s; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
 border-color: %(accent)s; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
 background: %(accent)s; border-color: %(accent)s; }

QTabWidget::pane { border: 1px solid %(border)s; border-radius: %(r)ipx;
 top: -1px; }
QTabBar::tab { background: %(bg_panel)s; color: %(status_fg)s;
 padding: 7px 16px; margin-right: 2px;
 border-top-left-radius: %(rs)ipx; border-top-right-radius: %(rs)ipx; }
QTabBar::tab:hover { background: %(bg_elevated)s; color: %(fg_browser)s; }
QTabBar::tab:selected { background: %(accent)s; color: #ffffff;
 font-weight: bold; }

QGroupBox { border: 1px solid %(border)s; border-radius: %(r)ipx;
 margin-top: 12px; padding: 14px 8px 8px 8px; }
QGroupBox::title { color: %(status_fg)s; subcontrol-origin: margin;
 left: 10px; padding: 0 4px; }

QMenu { background: %(menu_bg)s; color: %(menu_fg)s;
 border: 1px solid %(border_strong)s; border-radius: %(r)ipx; padding: 5px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: %(rs)ipx; margin: 1px 2px; }
QMenu::item:selected { background: %(menu_hover)s; color: #ffffff; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 10px; }

QToolTip { background: %(bg_elevated)s; color: %(fg_browser)s;
 border: 1px solid %(border_strong)s; border-radius: %(rs)ipx; padding: 5px 8px; }

QScrollBar:vertical { background: transparent; width: 10px;
 margin: 2px 2px 2px 0; }
QScrollBar:horizontal { background: transparent; height: 10px;
 margin: 0 2px 2px 2px; }
QScrollBar::handle:vertical { background: %(border_strong)s;
 border-radius: 5px; min-height: 32px; }
QScrollBar::handle:horizontal { background: %(border_strong)s;
 border-radius: 5px; min-width: 32px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
 background: %(accent)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: %(border)s; }
QProgressBar { background: %(bg_panel)s; border: 1px solid %(border)s;
 border-radius: %(rs)ipx; text-align: center; color: %(fg_browser)s; }
QProgressBar::chunk { background: %(accent)s; border-radius: %(rs)ipx; }
"""


def dialog_qss(t):
    """功能对话框(设置/模组管理/角色卡…)统一样式: 与主界面同色系。

    套在对话框顶层即可, 子控件按类型选择器自动继承。
    """
    return _DIALOG_QSS_TEMPLATE % dict(t, r=RADIUS, rs=RADIUS_SM)


def append_qss(base, extra):
    """把皮肤自定义 QSS 追加到基础样式后(空串安全)。"""
    extra = (extra or "").strip()
    return base + "\n" + extra if extra else base


_PANEL_QSS_TEMPLATE = """
ChatPanel { background: %(bg_window)s; color: %(fg_browser)s;
 font-family: '%(font_family)s'; font-size: %(font_size)spt; }

QPushButton { background: %(btn_bg)s; color: %(btn_fg)s;
 border: 1px solid %(border)s; border-radius: %(rs)ipx; padding: 5px 12px; }
QPushButton:hover { background: %(btn_hover)s; border-color: %(border_strong)s; }
QPushButton:pressed { background: %(accent_pressed)s; color: #ffffff;
 border-color: %(accent_pressed)s; }
QPushButton#btn_send { background: %(accent)s; color: #ffffff;
 border: 1px solid %(accent)s; border-radius: %(rs)ipx;
 padding: 6px 18px; font-weight: bold; }
QPushButton#btn_send:hover { background: %(accent_hover)s;
 border-color: %(accent_hover)s; }
QPushButton#btn_send:pressed { background: %(accent_pressed)s;
 border-color: %(accent_pressed)s; }

QLineEdit { background: %(bg_panel)s; color: %(fg_panel)s;
 border: 1px solid %(border)s; border-radius: %(rs)ipx; padding: 7px 10px;
 selection-background-color: %(accent)s; }
QLineEdit:focus { border-color: %(accent)s; background: %(bg_elevated)s; }

QComboBox { background: %(bg_panel)s; color: %(fg_panel)s;
 border: 1px solid %(border)s; border-radius: %(rs)ipx;
 padding: 5px 8px; min-width: 84px; }
QComboBox:hover { border-color: %(border_strong)s; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: %(bg_elevated)s; color: %(fg_panel)s;
 border: 1px solid %(border_strong)s; border-radius: %(rs)ipx;
 selection-background-color: %(accent)s; selection-color: #ffffff;
 padding: 4px; }

QTextBrowser { background: %(bg_browser)s; color: %(fg_browser)s;
 border: 1px solid %(border)s; border-radius: %(r)ipx; padding: 8px;
 selection-background-color: %(accent)s; }

QLabel#lbl_status { color: %(status_fg)s; font-size: 11px;
 padding: 2px 2px 0 2px; }

QMenu { background: %(menu_bg)s; color: %(menu_fg)s;
 border: 1px solid %(border_strong)s; border-radius: %(r)ipx; padding: 5px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: %(rs)ipx; margin: 1px 2px; }
QMenu::item:selected { background: %(menu_hover)s; color: #ffffff; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 10px; }

QToolTip { background: %(bg_elevated)s; color: %(fg_browser)s;
 border: 1px solid %(border_strong)s; border-radius: %(rs)ipx; padding: 5px 8px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 2px 2px 0; }
QScrollBar::handle:vertical { background: %(border_strong)s; border-radius: 5px;
 min-height: 32px; }
QScrollBar::handle:vertical:hover { background: %(accent)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


def panel_qss(t):
    """聊天面板整窗样式(一次 setStyleSheet 覆盖全部子控件)。"""
    return _PANEL_QSS_TEMPLATE % dict(t, r=RADIUS, rs=RADIUS_SM)


def bubble_qss(t):
    """桌宠头顶气泡: 半透明浮层, 圆角更大, 描边用主色。

    描边坚持用 accent 而不是中性描边色 —— 头顶气泡是桌宠最显眼的部件,
    主色描边才能让不同皮肤一眼可辨(测试也按这条契约校验)。
    """
    return (
        "QLabel {{ background: {bubble_bg}; color: {bubble_fg};"
        " border: 1px solid {accent}; border-radius: {r}px;"
        " padding: 9px 13px; }}"
    ).format(**dict(t, r=RADIUS_LG))


def chat_bubble_html(bg, fg, text, radius=RADIUS_LG):
    """聊天消息气泡的 HTML 片段(左右对齐由外层 div 决定)。"""
    return ('<span style="background:%s; color:%s; border-radius:%dpx;'
            ' padding:7px 11px; line-height:1.5;">%s</span>'
            % (bg, fg, radius, text))
