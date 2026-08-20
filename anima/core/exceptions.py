"""内核异常体系。

所有内核抛出的异常都继承 :class:`AnimaError`，调用方只需捕获这一个基类
即可区分"内核错误"与业务代码自身的异常。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "AnimaError",
    "DependencyError",
    "LifecycleError",
    "RollbackError",
    "ServiceExistsError",
    "ServiceNotFoundError",
]


class AnimaError(Exception):
    """所有内核异常的基类。"""


class DependencyError(AnimaError):
    """插件依赖解析失败：缺失依赖或存在循环依赖。"""


class ServiceExistsError(AnimaError):
    """向注册表重复注册同名服务。"""


class ServiceNotFoundError(AnimaError):
    """预留：按严格模式获取未注册服务时抛出。

    当前 :meth:`anima.core.registry.ServiceRegistry.use` 的契约是返回
    default 而非抛异常，此异常保留给未来的严格获取接口。
    """


class RollbackError(AnimaError):
    """副作用回滚阶段有一个或多个 cleanup 失败。

    回滚永不中断：所有失败项被收集到 :attr:`errors` 后统一抛出，
    ``__cause__`` 指向第一个子异常。
    """

    def __init__(self, errors: Sequence[BaseException], message: str | None = None) -> None:
        self.errors: list[BaseException] = list(errors)
        if message is None:
            names = "; ".join(repr(e) for e in self.errors)
            message = f"{len(self.errors)} 个清理操作失败: {names}"
        super().__init__(message)
        if self.errors:
            self.__cause__ = self.errors[0]


class LifecycleError(AnimaError):
    """插件生命周期状态机违规或插件元数据非法（如空 name、重名）。"""
