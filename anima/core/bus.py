"""事件总线：支持精确事件名与 ``前缀.*`` 通配符的发布订阅系统。

匹配规则:

- 精确订阅 ``"user.click"`` 只收到同名事件。
- 通配订阅 ``"user.*"`` 收到所有以 ``"user."`` 开头的事件，
  但不匹配裸事件名 ``"user"``。
- 通配订阅 ``"*"`` 收到一切事件。

执行顺序契约（v1.1.1 明确）: 精确订阅的 handler 先于通配 handler 执行，
两组各自内部按注册顺序执行；同步 handler 立即执行，协程 handler 的
执行时机由事件循环调度决定，与注册顺序无关。

优先级（v1.3 新增）: ``subscribe(..., priority=n)`` 让 n 大的先执行，同优先级仍
按注册顺序；只在真的用过非零 priority 时排序，"精确组先于通配组"不变。

单个 handler 抛异常不影响其他 handler 的执行：异常被隔离、交由
``on_error`` 钩子上报（默认写 ``anima.bus`` logger），不上抛给发布方。

线程语义（v1.1 文档化；v1.2 加锁强化）:

- 订阅表由 ``threading.RLock`` 保护，``subscribe`` / ``unsubscribe`` /
  ``count`` / ``clear`` / ``_handlers`` 都在锁内操作。因此**任意线程**
  增删订阅都是安全的——v1.1 时这条只靠"订阅只发生在内核线程"的口头
  约定，代码并不强制；v1.2 把它变成了机制。
- 锁**绝不跨越 handler 执行**：``_handlers`` 在锁内拷出列表后立即释放，
  handler 在**调用方线程**运行。所以 handler 里再 subscribe / emit 不会
  死锁，慢 handler 也不会阻塞其他线程的订阅。
- 单个 ``emit`` 调用仍是原子的：订阅表只在开头的``_handlers`` 里读一次，
  之后不再触碰；同步 handler 在调用方线程立即执行，协程 handler 只被
  调度、不被内联执行。
- 跨线程协程 handler **不会**被同步 ``emit`` 调度（调度依赖运行中的事件
  循环，``asyncio.get_running_loop`` 是线程局部的）。需要跨线程唤醒
  协程时用 ``loop.call_soon_threadsafe``——这条仍是使用者的责任。
- ``count()`` 是瞬时快照：并发增删下只保证"某一刻的近似值"。
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from anima.core.log import logger

Handler = Callable[[Any], Any]

#: handler 异常上报钩子，签名 ``(event, handler, exc) -> None``。
#:
#: 上报**不改变异常隔离语义**：异常依旧不会抛给 ``emit`` 的调用方，
#: 只是不再无声无息。
ErrorHook = Callable[[str, Handler, BaseException], None]

_log = logger.getChild("bus")

__all__ = ["ErrorHook", "EventBus"]


def _wildcard_prefix(pattern: str) -> str:
    """把 ``"user.*"`` 转换为前缀 ``"user."``（调用方已保证格式合法）。"""
    return pattern[:-1]


class EventBus:
    """进程内同步事件总线。

    精确事件走 ``dict`` 索引实现 O(1) 查找；通配订阅维护在独立的
    ``(前缀, handler)`` 列表中，emit 时线性扫描。

    单个 handler 抛出的异常被**隔离**（不上抛给发布方）并交给
    ``on_error`` 上报；未提供钩子时默认写 ``anima.bus`` logger。
    因此"订阅写错了"不会再完全无声。

    订阅表由 ``_lock`` 保护，且**绝不跨越 handler 执行**（见"线程语义"）。
    """

    def __init__(self, on_error: ErrorHook | None = None) -> None:
        # RLock：允许同线程重入，避免将来有人在锁内回调 handler 时死锁。
        self._lock = threading.RLock()
        self._seq = 0
        self._prioritized = False
        self._exact: dict[str, list[tuple[int, int, Handler]]] = {}
        self._wild: list[tuple[str, int, int, Handler]] = []
        self._on_error = on_error

    def set_error_hook(self, hook: ErrorHook | None) -> None:
        """替换（或清除）handler 异常上报钩子；``None`` 恢复默认 logger 上报。"""
        self._on_error = hook

    def _report(self, event: str, handler: Handler, exc: BaseException) -> None:
        """上报被隔离的 handler 异常。

        上报本身也必须遵守异常隔离不变式：钩子自己抛异常时退回默认
        logger，绝不让异常从 ``emit`` 漏给发布方。
        """
        try:
            if self._on_error is not None:
                self._on_error(event, handler, exc)
            else:
                _log.error("事件 handler 抛异常: event=%r handler=%r", event, handler, exc_info=exc)
        except Exception:
            _log.exception("异常上报钩子自身失败: event=%r", event)

    # -- 订阅管理 ---------------------------------------------------------

    def subscribe(self, event: str, handler: Handler, *, priority: int = 0) -> None:
        """订阅事件。``event`` 为 ``"*"`` 或 ``"前缀.*"`` 时按通配处理。

        任意线程可调用；``priority`` 越大越先执行（v1.3），默认 0 即注册顺序。
        """
        with self._lock:
            self._seq += 1
            if priority != 0:
                self._prioritized = True
            if event == "*":
                self._wild.append(("", priority, self._seq, handler))
                return
            if event.endswith(".*") and len(event) >= 2:
                self._wild.append((_wildcard_prefix(event), priority, self._seq, handler))
                return
            self._exact.setdefault(event, []).append((priority, self._seq, handler))

    def unsubscribe(self, event: str, handler: Handler) -> None:
        """取消订阅；订阅不存在时静默成功（幂等）。任意线程可调用。"""
        with self._lock:
            if event == "*" or (event.endswith(".*") and len(event) >= 2):
                prefix = "" if event == "*" else _wildcard_prefix(event)
                self._wild = [w for w in self._wild if not (w[0] == prefix and w[3] == handler)]
                return
            handlers = self._exact.get(event)
            if handlers is None:
                return
            for index, entry in enumerate(handlers):
                if entry[2] == handler:
                    del handlers[index]
                    break
            if not handlers:
                del self._exact[event]

    def count(self) -> int:
        """当前有效订阅总数（精确 + 通配）；并发增删下是瞬时快照。"""
        with self._lock:
            return sum(len(v) for v in self._exact.values()) + len(self._wild)

    # -- 发布 ---------------------------------------------------------

    def emit(self, event: str, data: Any = None) -> None:
        """同步发布事件。

        同步 handler 立即执行；协程 handler 调度到事件循环（无运行中的
        事件循环时静默丢弃并保持异常隔离）。单个 handler 的异常被隔离
        并经 ``_report`` 上报，不影响其他 handler。
        """
        for handler in self._handlers(event):
            try:
                result = handler(data)
            except Exception as exc:
                self._report(event, handler, exc)
                continue
            if asyncio.iscoroutine(result):
                _schedule_coroutine(result)

    def emit_async(self, event: str, data: Any = None) -> list[asyncio.Task[None]]:
        """异步发布事件。

        协程 handler 各自包装为 Task 立即返回；同步 handler 同步执行。
        返回创建的 Task 列表（无协程 handler 时为空列表）。同步 handler
        的异常同 :meth:`emit`：隔离并上报，不上抛。
        """
        tasks: list[asyncio.Task[None]] = []
        for handler in self._handlers(event):
            try:
                result = handler(data)
            except Exception as exc:
                self._report(event, handler, exc)
                continue
            if asyncio.iscoroutine(result):
                tasks.append(asyncio.ensure_future(result))
        return tasks

    async def emit_and_wait(self, event: str, data: Any = None) -> None:
        """异步发布并等待全部协程 handler 完成。

        :meth:`emit_async` 返回的 Task 列表一旦被调用方遗忘，就永远不会被
        await，任务可能在 GC 时被静默丢弃（Python 3.11 起才有告警）。本方法
        是那个常见用法的正确默认：调用方不必自己 ``gather``。协程 handler
        的异常按 handler 隔离（``return_exceptions=True``），与 :meth:`emit`
        的隔离语义一致。
        """
        tasks = self.emit_async(event, data)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def emit_collect(self, event: str, data: Any = None) -> list[Any]:
        """发布事件并收集**全部** handler 的返回值（请求-响应，v1.3）。

        同步返回值直接收集、协程结果 await 后收集，顺序即执行顺序。单个
        handler 的异常仍被隔离并上报：不产出结果，也不打断其余 handler。
        """
        results: list[Any] = []
        for handler in self._handlers(event):
            try:
                result = handler(data)
            except Exception as exc:
                self._report(event, handler, exc)
                continue
            if asyncio.iscoroutine(result):
                try:
                    results.append(await result)
                except Exception as exc:
                    self._report(event, handler, exc)
            else:
                results.append(result)
        return results

    def _handlers(self, event: str) -> list[Handler]:
        """锁内拷出本次发布要调用的 handler 列表——锁不跨越 handler 执行。

        只在用过非零 priority 时排序，全零时按注册顺序直接返回。
        """
        with self._lock:
            exact = list(self._exact.get(event, []))
            wild = [w for w in self._wild if event.startswith(w[0])]
            if self._prioritized:
                exact.sort(key=lambda e: (-e[0], e[1]))
                wild.sort(key=lambda w: (-w[1], w[2]))
            return [e[2] for e in exact] + [w[3] for w in wild]

    def clear(self) -> None:
        """移除全部订阅（框架 stop 时调用）。"""
        with self._lock:
            self._exact.clear()
            self._wild.clear()


def _schedule_coroutine(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return
    loop.create_task(coro)
