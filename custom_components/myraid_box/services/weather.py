from datetime import timedelta, datetime
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
            "url": {
                "name": "API地址",
                "description": "和风天气API地址",
                "required": True,
                "default": "https://devapi.qweather.com/v7/weather/3d",
                "type": "str"
            },
            "interval": {
                "name": "更新间隔(分钟)",
                "description": "数据更新间隔时间",
                "required": True,
                "default": 10,
                "type": "int"
            },
            "location": {
                "name": "城市ID",
                "description": "请输入城市LocationID",
                "required": True,
                "default": "",
                "type": "str"
            },
            "api_key": {
                "name": "API密钥",
                "description": "请输入和风天气API Key",
                "required": True,
                "default": "",
                "type": "password"
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
        async with coordinator.session.get(params["url"], params={
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
        
        return {
            "daily": raw_data.get("daily", []),
            "updateTime": raw_data.get("updateTime", "")
        }
    
    def get_sensor_configs(self, service_data: Any) -> list[Dict[str, Any]]:
        """始终返回3个天气传感器配置，无论数据是否存在"""
        day_names = ["今天", "明天", "后天"]
        
        return [{
            "key": f"day_{i}",
            "name": f"{self.name} {day_names[i]}",
            "icon": self.icon,
            "unit": self.unit,
            "device_class": self.device_class,
            "day_index": i,
            "day_name": day_names[i]
        } for i in range(3)]
    
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> Any:
        """格式化天气传感器值"""
        if not data or "daily" not in data:
            return "暂无天气数据"
            
        day_index = sensor_config.get("day_index", 0)
        day_name = sensor_config.get("day_name", "")
        
        if day_index >= len(data["daily"]):
            return f"{day_name}无数据"
            
        day_data = data["daily"][day_index]
        
        # 创建天气信息
        weather_info = [
            f"🌡️ 温度: {day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C",
            f"💧 湿度: {day_data.get('humidity', 'N/A')}%",
            f"🌧️ 降水: {day_data.get('precip', 'N/A')}mm",
            f"☁️ 云量: {day_data.get('cloud', 'N/A')}%",
            f"👀 能见度: {day_data.get('vis', 'N/A')}km",
            f"☀️ 紫外线: {day_data.get('uvIndex', 'N/A')}级",
            f"☀️ 白天: {day_data.get('textDay', 'N/A')} {day_data.get('windDirDay', 'N/A')} {day_data.get('windScaleDay', 'N/A')}级 {day_data.get('windSpeedDay', 'N/A')}km/h",
            f"🌙 夜间: {day_data.get('textNight', 'N/A')} {day_data.get('windDirNight', 'N/A')} {day_data.get('windScaleNight', 'N/A')}级 {day_data.get('windSpeedNight', 'N/A')}km/h"
        ]
        
        return "\n".join([line for line in weather_info if line is not None])
    
    def is_sensor_available(self, data: Any, sensor_config: Dict[str, Any]) -> bool:
        """检查天气传感器是否可用"""
        day_index = sensor_config.get("day_index", 0)
        if not data or "daily" not in data:
            return False
        return day_index < len(data["daily"])
    
    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气传感器额外属性"""
        if not data or "daily" not in data:
            return {}
            
        day_index = sensor_config.get("day_index", 0)
        if day_index >= len(data["daily"]):
            return {}
            
        day_data = data["daily"][day_index]
        attributes = {}
        
        for attr, attr_config in self.attributes.items():
            value = day_data.get(attr)
            if value is not None:
                # 特殊处理风力范围
                if attr in ["windScaleDay", "windScaleNight"]:
                    attributes[attr_config.get("name", attr)] = value
                else:
                    if "value_map" in attr_config:
                        value = attr_config["value_map"].get(str(value), value)
                    attributes[attr_config.get("name", attr)] = value
        
        # 添加日期信息
        if "fxDate" in day_data:
            attributes["日期"] = day_data["fxDate"]
        
        return attributes