"""插件抽象基类：插件与内核交互的唯一契约。

生命周期阶段约定：

- ``load()``: 只注册自己（provide 服务、订阅事件），不要 ``use()`` 别的
  插件的服务——依赖项此时可能尚未加载。
- ``enable()``: 依赖项已全部就绪，可以安全 ``use()``。
- ``disable()`` / ``unload()``: 框架会自动回滚 EffectTracker 记录的
  副作用，插件只需做自定义清理。

三个阶段方法都允许写成同步或异步（``def`` / ``async def``），
内核会统一调度。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anima.core.context import Context

__all__ = ["Plugin"]


class Plugin(ABC):
    """所有插件的基类。

    类属性:
        name: 插件唯一标识，注册时不能为空、不能重复。
        version: 插件版本号，仅用于展示。
        dependencies: 依赖的其他插件的 ``name`` 列表；空列表表示可独立加载。
    """

    name: str = ""
    version: str = "1.0.0"
    dependencies: list[str] = []

    @abstractmethod
    async def load(self, ctx: Context) -> None:
        """加载阶段：注册自身提供的服务与事件订阅。

        必须实现。此阶段不要使用其他插件的服务。
        """

    async def enable(self) -> None:
        """启用阶段：依赖已就绪，可安全使用其他插件的服务。默认空操作。"""

    async def disable(self) -> None:
        """禁用阶段：停止对外活动。框架随后自动回滚副作用。默认空操作。"""

    async def unload(self) -> None:
        """卸载阶段：最后的自定义清理。默认空操作。"""
