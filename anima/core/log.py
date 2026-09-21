"""结构化日志出口：内核日志统一挂在 ``"anima"`` 命名空间下。

内核遵循标准库的"库作者约定"：**不加 handler、不设级别**，把配置权
留给应用：

.. code-block:: python

    import logging

    logging.getLogger("anima").setLevel(logging.DEBUG)

子模块用 :func:`logging.Logger.getChild` 派生自己的 logger（如
``anima.bus``），层级过滤与全局过滤都可用；接入 structlog /
OpenTelemetry 时只需替换 ``anima`` 这棵子树的 handler。
"""

from __future__ import annotations

import logging

__all__ = ["logger"]

#: 内核统一日志出口；子模块用 ``logger.getChild("bus")`` 派生。
logger = logging.getLogger("anima")
