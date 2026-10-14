"""服务注册表 —— 运行时扫描 ``services/`` 目录自动发现 ``BaseService`` 子类。

设计要点：
- **单一职责**：本模块只负责"扫描 services/ → 建 SERVICE_REGISTRY"。
  ``const.py`` 只放纯数据，不含任何运行时行为。
- **幂等**：``discover_services()`` 首次调用扫描，之后 no-op；
  ``force=True`` 可强制重扫（调试 / 未来动态加载新服务）。
- **模块加载即扫描**：本文件末尾立即调用 ``discover_services()``，
  让下游 ``config_flow`` / ``coordinator`` / ``sensor`` 开箱即用，
  无需感知调用点。
- **容错**：单个服务模块 import 失败 / service_id 获取失败只记 warning，
  不中断整体注册流程。
- **无循环 import**：本文件依赖 ``.service_base.BaseService``（后者不依赖本文件），
  被扫描的服务模块也**只**依赖 ``const`` 而不依赖本文件，形成单向依赖。

新增服务：
    在 ``services/`` 下新建 ``xxx.py``，实现 ``BaseService`` 子类并覆写
    ``service_id`` property 即可。**无需修改本文件**，也无需修改
    ``const.py``。
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Dict, Type

from .service_base import BaseService

_LOGGER = logging.getLogger(__name__)

#: 服务注册表。首次模块加载时自动扫描填充。
SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}


def discover_services(force: bool = False) -> Dict[str, Type[BaseService]]:
    """扫描 ``services/`` 目录，把所有 ``BaseService`` 子类注册到
    ``SERVICE_REGISTRY``。

    :param force: 若为 ``True`` 则忽略当前注册表内容强制重扫（调试用）
    :returns: 更新后的注册表引用
    """
    global SERVICE_REGISTRY
    if SERVICE_REGISTRY and not force:
        return SERVICE_REGISTRY

    new_registry: Dict[str, Type[BaseService]] = {}
    services_dir = Path(__file__).parent / "services"

    if not services_dir.exists():
        _LOGGER.warning("services 目录不存在：%s", services_dir)
        return SERVICE_REGISTRY

    for mod_path in sorted(services_dir.glob("*.py")):
        if mod_path.name.startswith(("_", ".")):
            continue
        module_name = f"{__package__}.services.{mod_path.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception:
            _LOGGER.exception("加载服务模块 %s 失败，跳过", module_name)
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseService)
                and attr is not BaseService
            ):
                try:
                    sid = attr().service_id
                except Exception:
                    _LOGGER.exception("获取 %s.service_id 失败，跳过", attr_name)
                    continue
                if sid in new_registry:
                    _LOGGER.warning(
                        "service_id `%s` 重复（%s 与 %s），保留先注册的",
                        sid,
                        new_registry[sid].__name__,
                        attr_name,
                    )
                    continue
                new_registry[sid] = attr

    SERVICE_REGISTRY = new_registry
    _LOGGER.info(
        "服务注册完成，共 %d 个：%s",
        len(SERVICE_REGISTRY),
        list(new_registry.keys()),
    )
    return SERVICE_REGISTRY


# 模块加载时立即执行一次扫描，让所有下游 import 者开箱即用。
# 这样 config_flow.py / coordinator.py / sensor.py 无需感知调用点，
# 也避免了「谁先 import 谁负责 bootstrap」的隐式耦合。
discover_services()
