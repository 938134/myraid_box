from datetime import timedelta
from typing import Dict, Any, Optional
from ..service_base import BaseService, AttributeConfig
from ..const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL

class WeatherService(BaseService):
    """每日天气服务"""
    
    @property
    def service_id(self) -> str:
        return "weather"
    
    @property
    def name(self) -> str:
        return "每日天气"
    
    @property
    def description(self) -> str:
        return "获取最新天气信息(和风天气)"
    
    @property
    def url(self) -> str:
        return "https://devapi.qweather.com/v7/weather/3d"
    
    @property
    def interval(self) -> timedelta:
        return timedelta(minutes=10)
    
    @property
    def icon(self) -> str:
        return "mdi:weather-partly-cloudy"
    
    @property
    def unit(self) -> str:
        return None
    
    @property
    def device_class(self) -> str:
        return None
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
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
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "tempMax": {
                "name": "最高温度",
                "icon": "mdi:thermometer-high",
                "unit": "°C",
                "device_class": "temperature"
            },
            "tempMin": {
                "name": "最低温度",
                "icon": "mdi:thermometer-low",
                "unit": "°C",
                "device_class": "temperature"
            },
            "textDay": {
                "name": "白天天气",
                "icon": "mdi:weather-sunny"
            },
            "windDirDay": {
                "name": "白天风向",
                "icon": "mdi:weather-windy"
            },
            "windScaleDay": {
                "name": "白天风力",
                "icon": "mdi:weather-windy",
                "unit": None, 
                "value_map": { 
                    "1-3": "1-3级",
                    "4-6": "4-6级"
                }
            },
            "windSpeedDay": {
                "name": "白天风速",
                "icon": "mdi:weather-windy",
                "unit": "km/h"
            },
            "textNight": {
                "name": "夜间天气",
                "icon": "mdi:weather-night"
            },
            "windDirNight": {
                "name": "夜间风向",
                "icon": "mdi:weather-windy"
            },
            "windScaleNight": {
                "name": "夜间风力",
                "icon": "mdi:weather-windy",
                "unit": None,  
                "value_map": { 
                    "1-3": "1-3级",
                    "4-6": "4-6级"
                }
            },
            "windSpeedNight": {
                "name": "夜间风速",
                "icon": "mdi:weather-windy",
                "unit": "km/h"
            },
            "precip": {
                "name": "降水量",
                "icon": "mdi:weather-rainy",
                "unit": "mm"
            },
            "uvIndex": {
                "name": "紫外线指数",
                "icon": "mdi:weather-sunny-alert"
            },
            "humidity": {
                "name": "湿度",
                "icon": "mdi:water-percent",
                "unit": "%"
            },
            "pressure": {
                "name": "大气压",
                "icon": "mdi:gauge",
                "unit": "hPa"
            },
            "vis": {
                "name": "能见度",
                "icon": "mdi:eye",
                "unit": "km"
            },
            "cloud": {
                "name": "云量",
                "icon": "mdi:weather-cloudy",
                "unit": "%"
            }
        }
    
    async def fetch_data(self, coordinator, params):
        """获取天气数据"""
        async with coordinator.session.get(self.url, params={
            "location": params["location"],
            "key": params["api_key"],
            "lang": "zh",
            "unit": "m"
        }) as resp:
            data = await resp.json()
            return self._process_weather_data(data)
    
    def _process_weather_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理天气数据"""
        if not raw_data or "daily" not in raw_data:
            return {}
        
        # 获取今天和明天的天气预报
        daily_data = raw_data.get("daily", [])
        today = daily_data[0] if daily_data else {}
        tomorrow = daily_data[1] if len(daily_data) > 1 else {}
        
        return {
            "today": today,
            "tomorrow": tomorrow,
            "daily": daily_data,
            "updateTime": raw_data.get("updateTime", "")
        }
    
    def format_main_value(self, data):
        """格式化主传感器显示"""
        if not data or "today" not in data:
            return "暂无天气数据"
        
        today = data["today"]
        return f"{today.get('tempMin', 'N/A')}~{today.get('tempMax', 'N/A')}°C"
    
    def get_attribute_value(self, data: Any, attribute: str) -> Any:
        """获取属性值"""
        if not data or "today" not in data:
            return None

        value = data["today"].get(attribute)
        
        # 特殊处理风力范围
        if attribute in ["windScaleDay", "windScaleNight"]:
            return value  # 直接返回原始字符串（如 "1-3"）
        
        return value