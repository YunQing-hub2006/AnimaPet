# -*- coding: utf-8 -*-
"""统一日志: 写到 data/ 下的 pet.log, 任何错误只记录不影响运行。

与 YingPet 不同点: 模块导入时不再无条件配置 root logger(测试环境会
被日志文件污染), 提供 :func:`setup` 由 main.py 显式初始化; 未初始化
前 ``get`` 返回普通 logger 走 stderr。
"""
import logging

from . import paths

_configured = False


def setup():
    """初始化 root logger 写文件; 幂等, main.py 启动时调用一次。"""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        filename=paths.LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
        encoding="utf-8",
    )
    _configured = True


def get(name):
    return logging.getLogger(name)
