"""服务注册表：插件间服务发现的中心枢纽。"""

from __future__ import annotations

from typing import Any

from anima.core.exceptions import ServiceExistsError

__all__ = ["ServiceRegistry"]


class ServiceRegistry:
    """按名字注册 / 发现服务实例。

    - 重复注册同名服务抛 :class:`ServiceExistsError`。
    - ``unregister`` 不存在的名字静默成功（幂等）。
    - ``use`` 返回实例本身，不做任何包装。
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, instance: Any) -> None:
        """注册服务；名字已被占用时抛 :class:`ServiceExistsError`。"""
        if name in self._services:
            raise ServiceExistsError(f"服务已注册: {name!r}")
        self._services[name] = instance

    def unregister(self, name: str) -> None:
        """注销服务；名字不存在时静默成功（幂等）。"""
        self._services.pop(name, None)

    def use(self, name: str, default: Any = None) -> Any:
        """获取服务实例；未注册时返回 ``default``。"""
        return self._services.get(name, default)

    def has(self, name: str) -> bool:
        """服务是否已注册。"""
        return name in self._services

    def list(self) -> list[str]:
        """当前全部服务名的快照（新建列表，修改不影响注册表）。"""
        return list(self._services)

    def clear(self) -> None:
        """注销全部服务（框架 stop 时调用）。"""
        self._services.clear()
