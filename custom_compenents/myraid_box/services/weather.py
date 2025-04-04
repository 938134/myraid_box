import logging
from datetime import timedelta
from typing import Any, Dict
from .base import BaseService
from ..const import register_service

_LOGGER = logging.getLogger(__name__)

@register_service(
    name="每日天气",
    description="获取最新天气信息(和风天气)",
    url="https://devapi.qweather.com/v7/weather/3d",
    interval=timedelta(minutes=10),
    icon="mdi:weather-partly-cloudy",
    attributes={
        "tempMax": {
            "name": "最高温度",
            "icon": "mdi:thermometer-high",
            "unit": "°C"
        },
        "tempMin": {
            "name": "最低温度",
            "icon": "mdi:thermometer-low",
            "unit": "°C"
        },
        # ...其他天气属性...
    }
)
class WeatherService(BaseService):
    async def async_update_data(self) -> Dict[str, Any]:
        """获取天气数据"""
        params = {
            "location": self._config.get("weather_location", ""),
            "key": self._config.get("weather_api_key", ""),
            "lang": "zh",
            "unit": "m"
        }
        
        try:
            async with self.session.get(
                ServiceRegistry.get("weather")["url"],
                params=params
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            _LOGGER.error(f"获取天气数据失败: {str(e)}")
            return {"error": str(e)}
    
    @classmethod
    def config_fields(cls) -> Dict[str, Dict[str, Any]]:
        """天气服务配置字段"""
        return {
            "location": {
                "display_name": "城市ID",
                "description": "请输入城市LocationID",
                "required": True,
                "default": ""
            },
            "api_key": {
                "display_name": "API密钥",
                "description": "请输入和风天气API Key",
                "required": True,
                "default": ""
            }
        }