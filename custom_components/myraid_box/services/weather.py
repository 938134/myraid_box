from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import logging
import aiohttp
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"

class WeatherService(BaseService):
    """增强版天气服务"""

    def __init__(self):
        super().__init__()
        self._valid_domains = ["devapi.qweather.com", "api.qweather.com"]
        self._session = None

    @property
    def service_id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "每日天气"

    @property
    def description(self) -> str:
        return "3天天气预报（支持自定义API）"

    @property
    def icon(self) -> str:
        return "mdi:weather-partly-cloudy"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": DEFAULT_WEATHER_API,
                "description": "官方或备用地址\n示例:\n- 官方: https://devapi.qweather.com/v7/weather/3d\n- 备用: https://api.qweather.com/v7/weather/3d",
                "regex": r"^https?://(devapi|api)\.qweather\.com/v7/weather/\d+d?$",
                "placeholder": DEFAULT_WEATHER_API
            },
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": 30,
                "min": 10,
                "max": 240,
                "unit": "分钟",
                "description": "建议30-60分钟"
            },
            "location": {
                "name": "位置ID",
                "type": "str",
                "required": True,
                "description": "和风天气LocationID",
                "example": "101010100"
            },
            "api_key": {
                "name": "API密钥",
                "type": "password",
                "required": True,
                "description": "和风天气开发者Key"
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "tempMax": {"name": "最高温度", "icon": "mdi:thermometer-plus", "unit": "°C"},
            "tempMin": {"name": "最低温度", "icon": "mdi:thermometer-minus", "unit": "°C"},
            # ...其他属性...
            "api_source": {"name": "数据源", "icon": "mdi:server-network"}
        }

    async def ensure_session(self):
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15))
            _LOGGER.debug("创建新的天气API会话")

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据（带验证）"""
        await self.ensure_session()
        url = params["url"].strip()
        
        if not self._validate_url(url):
            raise ValueError(f"无效的API地址: {url}")

        try:
            _LOGGER.debug("正在获取天气数据，位置: %s", params["location"])
            async with self._session.get(url, params={
                "location": params["location"],
                "key": params["api_key"],
                "lang": "zh",
                "unit": "m"
            }) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                if "daily" not in data:
                    raise ValueError("API响应缺少daily字段")
                    
                return {
                    "api_source": urlparse(url).netloc,
                    "update_time": data.get("updateTime", datetime.now().isoformat()),
                    "forecast": data["daily"],
                    "status": "success"
                }
                
        except Exception as e:
            _LOGGER.error("天气数据获取失败: %s", str(e), exc_info=True)
            return {
                "error": str(e),
                "api_source": urlparse(url).netloc,
                "update_time": datetime.now().isoformat(),
                "status": "error"
            }

    def _validate_url(self, url: str) -> bool:
        """验证URL合法性"""
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ("http", "https"),
                parsed.netloc in self._valid_domains,
                parsed.path.startswith("/v7/weather/")
            ])
        except:
            return False

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """3天预报传感器配置"""
        return [{
            "key": f"day_{i}",
            "name": f"{self.name} {['今天','明天','后天'][i]}",
            "icon": ["mdi:calendar-today", "mdi:calendar-arrow-right", "mdi:calendar-end"][i],
            "day_index": i,
            "device_class": "weather"
        } for i in range(3)]

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """优化天气信息显示"""
        if not data or not data.get("forecast"):
            return "⏳ 获取天气中..."
            
        day_data = self._get_day_data(data["forecast"], sensor_config.get("day_index", 0))
        if not day_data:
            return "⚠️ 无数据"
            
        lines = [
            f"☁ {day_data.get('textDay', '未知')}/{day_data.get('textNight', '未知')}",
            f"🌡 {day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C",
            f"💧 湿度: {day_data.get('humidity', 'N/A')}%",
            f"🌧 降水: {day_data.get('precip', '0')}mm"
        ]
        return "\n".join(lines)

    def _get_day_data(self, forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天数据"""
        try:
            return forecast[index]
        except (IndexError, TypeError):
            return None

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """增强天气属性"""
        attrs = {
            "api_source": data.get("api_source"),
            "update_time": data.get("update_time")
        }
        
        day_data = self._get_day_data(data.get("forecast", []), sensor_config.get("day_index", 0))
        if day_data:
            for attr, config in self.attributes.items():
                if attr in day_data:
                    attrs[config["name"]] = day_data[attr]
            attrs["日期"] = day_data.get("fxDate", "")
            
        return attrs

    async def async_unload(self):
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("天气服务会话已关闭")