"""ServiceCoordinator：单个服务的 DataUpdateCoordinator 子类。

从 ``__init__.py`` 抽出到独立模块，理由：
- ``ServiceCoordinator`` 是**基础设施**，被 ``sensor.py`` / ``api_view.py`` /
  ``config_flow.py`` 类型引用；放在 ``__init__.py`` 会与这些模块产生循环引用隐患。
- 拆分后 ``__init__.py`` 只保留"入口"逻辑（setup / unload / 类型别名），
  职责更清晰。

命名与依赖：
- 依赖 ``.const.SERVICE_REGISTRY`` 拿到目标 service 类。
- 依赖 ``.service_base.BaseService`` 作为类型注解。
- ``MyraidBoxConfigEntry`` 只在类型注解里出现，用 ``TYPE_CHECKING`` 隔离，
  避免运行时循环 import（``__init__.py`` 会反过来 ``from .coordinator import``）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .registry import SERVICE_REGISTRY
from .service_base import BaseService

if TYPE_CHECKING:  # pragma: no cover - 类型检查专用，运行时不导入
    from . import MyraidBoxConfigEntry

_LOGGER = logging.getLogger(__name__)


class ServiceCoordinator(DataUpdateCoordinator):
    """单个服务的协调器，持有唯一 service 实例。

    职责：
    - 从 ``SERVICE_REGISTRY`` 拿 service 类，注入 ``hass`` 并实例化
    - 从 ``entry.data`` 提取 ``<service_id>_`` 前缀的字段作为 params
    - 定期调用 ``service.fetch_data``，包裹在 ``asyncio.wait_for`` 里
    - 暴露 ``service`` 属性给 sensor 复用同一实例（避免每个 sensor 各建一个）
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MyraidBoxConfigEntry,
        service_id: str,
    ) -> None:
        service_class = SERVICE_REGISTRY[service_id]
        # 关键：注入 hass，service 通过 async_get_clientsession 复用全局 session
        self.service: BaseService = service_class(hass=hass)
        self.service_id = service_id
        self.entry = entry

        prefix = f"{service_id}_"
        self.params = {
            k[len(prefix):]: v
            for k, v in entry.data.items()
            if k.startswith(prefix)
        }

        interval_minutes = int(
            self.params.get(
                "interval",
                self.service.config_fields.get("interval", {}).get("default", 15),
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{service_id}",
            update_interval=timedelta(minutes=interval_minutes),
            update_method=self._async_update_data,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        update_time = datetime.now().isoformat()
        # 外层 timeout = 内部 aiohttp 超时的 1.2 倍作为兜底，
        # 覆盖 TLS 握手 / DNS 解析等"内部超时未感知"的场景。
        # 不再使用 "+5s"：内部已超时抛错时再等 5 秒是多余阻塞。
        outer_timeout = self.service.default_timeout * 1.2
        try:
            result = await asyncio.wait_for(
                self.service.fetch_data(self, self.params),
                timeout=outer_timeout,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("[%s] 更新超时", self.service_id)
            raise
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", self.service_id, e, exc_info=True)
            raise

        result["update_time"] = update_time
        return result

    # 暴露给 sensor 使用：单一 service 实例，避免每个 sensor 各建一个
    @property
    def service_config(self) -> BaseService:
        return self.service
