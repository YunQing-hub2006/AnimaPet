# -*- coding: utf-8 -*-
"""角色卡管理器 (自 YingPet-v4 feature.charcard 平移)。

数据源: module_manager 服务(mm)+ registry/config 服务; 保存动作统一经
anima.models.load_card 整体预检(坏数据弹错不落盘); 重扫走
mm.rescan()(线程感知)+ 跨线程等待(_wait_fire 模式, 与 modmanager 一致)。
"""
import asyncio


def wait_fire(fut, timeout=10):
    """等待 fire()/rescan() 的调度结果(与 ModsDialog._wait_fire 等价)。

    fire 有两种返回: 跨线程(生产, Qt 线程) → concurrent Future(带超时);
    单线程测试 → asyncio.Task(result() 不接受超时参数, 未完成抛
    InvalidStateError, 由外层事件循环推动, 调用方 await 后再断言)。
    """
    if fut is None:   # 内核线程已同步执行
        return
    if isinstance(fut, asyncio.Task):
        try:
            fut.result()
        except asyncio.InvalidStateError:
            pass
        except Exception:
            raise
    else:
        fut.result(timeout)


def wait_rescan(fut):
    """等待 rescan 完成(上限 10s); 失败只记日志, 不打断对话框。"""
    try:
        wait_fire(fut, timeout=10)
    except Exception:
        pass