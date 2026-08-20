"""副作用追踪器：插件卸载时自动、完整、异常安全地回滚全部副作用。"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from anima.core.exceptions import RollbackError

if TYPE_CHECKING:
    from anima.core.bus import EventBus
    from anima.core.registry import ServiceRegistry

CleanupFn = Callable[[], None] | Callable[[], Awaitable[None]]

__all__ = ["EffectTracker", "CleanupFn"]


class EffectTracker:
    """以 LIFO 栈记录回滚操作，插件卸载时逆序执行。

    单个 cleanup 失败不会中断后续回滚；所有异常收集完毕后统一以
    :class:`RollbackError` 抛出。
    """

    def __init__(self) -> None:
        self._stack: list[CleanupFn] = []

    def push(self, rollback: CleanupFn) -> None:
        """压入一个回滚操作；同一函数重复压入会被记录多次。"""
        self._stack.append(rollback)

    def push_task(self, task: asyncio.Future[Any]) -> asyncio.Future[Any]:
        """登记一个后台任务，回滚时取消并等待其真正结束。

        已完成的任务登记后 rollback 是空操作；任务自身的异常（取消
        之外）会进入 :class:`RollbackError` 聚合。
        """
        if not isinstance(task, asyncio.Future):
            raise TypeError(f"push_task 需要 asyncio.Future/Task，得到 {type(task).__name__}")

        async def _cancel_and_await() -> None:
            if not task.done():
                # 先让出一个循环节拍：cancel 落在从未启动的协程上时，
                # 异常在函数定义点抛出，协程体（含 finally）不会执行。
                await asyncio.sleep(0)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            else:
                # 已结束的任务：re-raise 让 rollback 感知失败（若有）
                await task

        self.push(_cancel_and_await)
        return task

    def on(self, target: "EventBus", event: str, handler: Callable[[Any], Any]) -> None:
        """订阅事件并自动记录对应的取消订阅。"""
        target.subscribe(event, handler)
        self.push(lambda: target.unsubscribe(event, handler))

    def provide(self, registry: "ServiceRegistry", name: str, instance: Any) -> None:
        """注册服务并自动记录对应的注销。"""
        registry.register(name, instance)
        self.push(lambda: registry.unregister(name))

    async def rollback(self) -> None:
        """逆序执行全部回滚操作并清空栈。

        有失败项时抛 :class:`RollbackError`（其 ``errors`` 属性是全部
        子异常列表）；栈为空时静默返回。
        """
        errors: list[BaseException] = []
        while self._stack:
            cleanup = self._stack.pop()
            try:
                result = cleanup()
            except Exception as exc:
                errors.append(exc)
                continue
            if inspect.isawaitable(result):
                try:
                    await result
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise RollbackError(errors)

    def count(self) -> int:
        """尚未回滚的副作用数量。"""
        return len(self._stack)

    def clear(self) -> None:
        """清空栈但不执行任何回滚操作。"""
        self._stack.clear()
