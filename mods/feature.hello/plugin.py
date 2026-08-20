# -*- coding: utf-8 -*-
"""演示功能模组: 向右键菜单添加『打个招呼』。

AnimaPet 功能模组契约(自 YingPet-v4 平移, 类名/回调名不变):
- plugin.py 定义 class Feature(id/name + on_load/on_enable/on_disable)
- on_load 收到白名单 FeatureContext, 可用:
    add_menu_action  向右键菜单注入功能
    say/emote        驱动宠物表现(经 bridge 封送到 Qt 线程)
    emit/on          收发事件(可被行为规则监听; on 的订阅卸载自动回滚)
    get_state/set_state  持久化状态(热重载不丢失)
    data             跨热重载的私有数据容器
"""


class Feature:
    id = "feature.hello"
    name = "打招呼演示"

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.add_menu_action("打个招呼 (插件)", self._hello)
        ctx.log("已加载")

    def _hello(self):
        count = int(self.ctx.get_state("hello_count") or 0) + 1
        self.ctx.set_state("hello_count", count)
        self.ctx.emit("feature.hello.clicked", {"count": count})
        self.ctx.say("你好呀。这是第 %d 次由插件触发的台词。" % count)
        self.ctx.emote("mischief", after_ms=1000)
