# -*- coding: utf-8 -*-
"""事件名常量表: 沿用 YingPet-v4 的事件命名, 行为模组的 rules 兼容。

总线本身是任意字符串; 这里集中声明官方事件, 供 IDE 补全与文档检索。
"""


class EventNames:
    APP_START = "app.start"
    APP_QUIT = "app.quit"
    PET_CLICKED = "pet.clicked"
    PET_DOUBLE_CLICKED = "pet.double_clicked"
    PET_DRAG_STARTED = "pet.drag_started"   # payload: {}
    PET_DRAG_ENDED = "pet.drag_ended"
    PET_PETTED = "pet.petted"               # payload: {affinity}
    STATE_CHANGED = "state.changed"         # payload: {key, value}
    CHAT_SEND = "chat.send"                 # payload: {text}
    CHAT_REPLY = "chat.reply"               # payload: {ok, emotion, text}
    BUBBLE_FINISHED = "bubble.finished"
    EMOTE_SHOWN = "emote.shown"             # payload: {emote}
    TIMER_IDLE = "timer.idle"               # 随机搭话节拍
    TIMER_SIT = "timer.sit"                 # 久坐节拍(45 分钟)
    TIMER_NIGHT = "timer.night"             # 深夜(每夜一次)
    MODS_RELOADED = "mods.reloaded"
    FEATURE_DISABLING = "feature.disabling"  # payload: {feature}
    CHARACTER_SWITCHED = "character.switched"  # payload: {character}
    CHARACTER_SWITCH = "character.switch"      # 插件->窗口, payload: {character}
    UI_CHANGED = "ui.changed"                  # payload: {ui}
    PLUGIN_ENABLED = "plugin.enabled"           # payload: {plugin}
    PLUGIN_DISABLED = "plugin.disabled"        # payload: {plugin}
