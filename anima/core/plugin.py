"""插件抽象基类：插件与内核交互的唯一契约。

生命周期阶段约定：

- ``load()``: 只注册自己（provide 服务、订阅事件），不要 ``use()`` 别的
  插件的服务——依赖项此时可能尚未加载。
- ``enable()``: 依赖项已全部就绪，可以安全 ``use()``。
- ``disable()``: 暂停对外活动。**副作用保留**——事件订阅仍在、服务
  仍处于注册状态，事件依旧会投递到插件自己的 handler；插件应自行用
  状态位决定是否响应。回滚不发生在这一步。
- ``unload()``: 最终清理。框架在这里统一回滚 EffectTracker 记录的
  全部副作用（取消订阅、注销服务、取消后台任务），随后才调用插件
  自己的 ``unload()``。

因此 ``disable()`` 与 ``unload()`` 的分工是：前者停止"主动做事"
（循环、定时器、对外请求），后者才卸下"向内注册"的东西。

三个阶段方法都允许写成同步或异步（``def`` / ``async def``），
内核会统一调度。

框架在调用 ``load()`` **之前**把当前 :class:`Context` 注入
``self.ctx``（v1.2），因此 ``load`` / ``enable`` / ``disable`` / ``unload`` 全阶段都能直接用
``self.ctx``，不必再自己写 ``self._ctx = ctx``。重启（stop 后再 start）
会用新的 Context 覆盖它。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from anima.core.context import Context

__all__ = ["Plugin"]


class Plugin(ABC):
    """所有插件的基类。

    类属性:
        name: 插件唯一标识，注册时不能为空、不能重复。
        version: 插件版本号，仅用于展示。
        dependencies: 依赖的其他插件的 ``name``；空表示可独立加载。
            默认值是**不可变元组**，子类不会共享同一个可变对象
            （元组或列表都可赋值；列表在声明式元数据下同样安全）。
        config_defaults: 配置项及默认值（v1.3）；框架在 ``load()`` 前把缺失的
            key 填进 ``ctx.config``。只声明，默认值是不可写映射。
        ctx: 框架在 ``load()`` 前注入的 Context（v1.2）。**保留属性名**：
            子类不要声明自己的 ``ctx``——只读 property 会让注入直接失败。
    """

    name: str = ""
    version: str = "1.0.0"
    dependencies: ClassVar[Sequence[str]] = ()
    config_defaults: ClassVar[Mapping[str, Any]] = MappingProxyType({})

    if TYPE_CHECKING:
        #: 框架在 ``load()`` 前注入（v1.2）；``ctx`` 是**保留属性名**（见类 docstring）。
        #: 只在类型检查期声明，运行时不产生类属性——避免契约层反向 import
        #: 编排层（见架构 §2）。
        ctx: Context

    @abstractmethod
    async def load(self, ctx: Context) -> None:
        """加载阶段：注册自身提供的服务与事件订阅。

        必须实现。此阶段不要使用其他插件的服务。
        """

    async def enable(self) -> None:
        """启用阶段：依赖已就绪，可安全使用其他插件的服务。默认空操作。"""

    async def disable(self) -> None:
        """禁用阶段：停止对外活动。

        默认空操作。**副作用不回滚**——``ctx.on`` / ``ctx.provide`` 登记
        的订阅与注册会保留到 ``unload()``；禁用期间事件仍会投递到本
        插件的 handler，是否响应由插件自己的状态位决定。
        """

    async def unload(self) -> None:
        """卸载阶段：最后的自定义清理。默认空操作。"""
