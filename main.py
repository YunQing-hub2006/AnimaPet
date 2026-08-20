# -*- coding: utf-8 -*-
"""AnimaPet 入口: 单实例锁 + Qt 主线程 + 内核 asyncio daemon 线程(TD1-A)。

启动序(HANDOVER §四.1 / §五):

1. Win32 命名互斥量单实例锁(``AnimaPetSingleton``);
2. QApplication + ``sys.excepthook`` 最后防线(记录不闪退);
3. **Qt 线程**先建共享服务(config/state/registry/actions)与 PetWindow,
   引用传给 BridgePlugin;
4. 内核 asyncio 循环起在 daemon 线程, 驱动 ``app.start(plugins)``;
5. 内核就绪后 ``pet.show()`` → ``app.exec()``; 退出前广播 app.quit 并停循环。

线程规则: UI 线程只 emit; 内核线程动 UI 走 ``bridge.run_on_ui``。
"""
import asyncio
import ctypes
import sys
import threading
import traceback


def _fatal(msg):
    """启动失败时用系统消息框提示(pythonw 无控制台, 静默失败最坑)。"""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(msg), "AnimaPet", 0x10)
    except Exception:
        pass


def _acquire_singleton():
    """单实例保护: 命名互斥量是内核对象, 进程退出(哪怕强杀)自动释放, 无残留锁文件。"""
    ctypes.windll.kernel32.CreateMutexW(None, False, "AnimaPetSingleton")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        _fatal("AnimaPet 已经在运行啦。\n(看看屏幕右下角, 别慌, 它就在那)")
        sys.exit(0)

try:
    from PyQt6.QtWidgets import QApplication
except Exception as e:
    _fatal("缺少 PyQt6 依赖, 无法启动。\n请用 run.bat 启动(它会使用自带的 Python 环境)。\n\n错误: %s" % e)
    sys.exit(1)

from anima.core import App
from anima.events import EventNames
from anima.mods.registry import Registry
from anima.plugins.actions import ActionRegistry, ActionsPlugin
from anima.plugins.bridge import BridgePlugin
from anima.plugins.character_manager import CharacterManagerPlugin
from anima.plugins.config import ConfigPlugin, ConfigService
from anima.plugins.hotreload import HotreloadPlugin
from anima.plugins.loader import LoaderPlugin
from anima.plugins.module_manager import ModuleManagerPlugin
from anima.plugins.rule_engine import RuleEnginePlugin
from anima.plugins.state import StatePlugin, StateService
from anima.utils import log, paths
from anima.window.pet_window import PetWindow

_log = log.get("main")


def _build_stack():
    """在 Qt 主线程构建共享服务 + PetWindow + 全部官方插件(TD1-A: 先建窗口再 start)。"""
    core = App()
    cfg = ConfigService()
    cfg.load()
    state = StateService()
    state.load()
    registry = Registry()
    actions = ActionRegistry()
    pet = PetWindow(registry, core.bus, cfg, state, actions=actions)
    bridge = BridgePlugin(pet)
    plugins = [
        ConfigPlugin(cfg),
        StatePlugin(state),
        ActionsPlugin(actions),
        LoaderPlugin(registry),
        RuleEnginePlugin(),
        CharacterManagerPlugin(),
        bridge,
        ModuleManagerPlugin(),
        HotreloadPlugin(),
    ]
    return core, plugins, pet, bridge


def _kernel_main(core, plugins, holder):
    """内核线程入口: 起 asyncio 循环 → app.start → 通知主线程 → run_forever。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    holder["loop"] = loop
    # 把内核循环注入 module_manager: Qt 线程的 fire()/rescan() 跨线程投递依赖它
    for plugin in plugins:
        if plugin.name == "module_manager":
            plugin.service.bind_loop(loop)
    try:
        loop.run_until_complete(core.start(plugins))
        holder["started"].set()
        loop.run_forever()
    except Exception as e:   # 内核起不来: 报错并放行主线程退出
        holder["error"] = e
        holder["started"].set()
        _log.error("kernel failed: %s", e)
    finally:
        try:
            loop.run_until_complete(core.stop())
        except Exception as e:
            _log.warning("kernel stop: %s", e)
        loop.close()
        holder["loop"] = None


def main():
    _acquire_singleton()
    try:
        _run()
    except Exception:
        _fatal("程序启动失败:\n\n" + traceback.format_exc())
        sys.exit(1)


def _run():
    log.setup()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    def excepthook(tp, val, tb):
        _log.error("UNCAUGHT: %s", "".join(traceback.format_exception(tp, val, tb)))
        # 不退出, 只记录 —— 不闪退的最后一道防线

    sys.excepthook = excepthook

    core, plugins, pet, _bridge = _build_stack()
    holder = {"loop": None, "started": threading.Event(), "error": None}
    thread = threading.Thread(
        target=_kernel_main, args=(core, plugins, holder),
        daemon=True, name="anima-kernel")
    thread.start()
    holder["started"].wait(timeout=15)
    if holder["error"] is not None:
        raise holder["error"]
    if holder["loop"] is None:
        raise RuntimeError("内核线程未在 15 秒内就绪")

    pet.show()
    _log.info("AnimaPet started at %s", paths.BASE_DIR)
    core.bus.emit(EventNames.APP_START)

    def on_quit():
        core.bus.emit(EventNames.APP_QUIT)
        loop = holder.get("loop")
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)

    app.aboutToQuit.connect(on_quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
