from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"

class WeatherService(BaseService):
    """增强版天气服务 - 最终版"""

    @property
    def service_id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "每日天气"

    @property
    def description(self) -> str:
        return "从和风天气获取3天天气预报"

    @property
    def icon(self) -> str:
        return "mdi:weather-partly-cloudy"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_WEATHER_API,
                "description": "官方或备用地址"
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 30,
                "description": "更新间隔时间"
            },
            "location": {
                "name": "城市ID",
                "type": "str",
                "default": "101010100",
                "description": "和风天气LocationID"
            },
            "api_key": {
                "name": "API密钥",
                "type": "password",
                "default": "",
                "description": "和风天气开发者Key"
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        base_attrs = {
            "textDay": {
                "name": "白天天气",
                "icon": "mdi:weather-sunny"
            },
            "textNight": {
                "name": "夜间天气",
                "icon": "mdi:weather-night"
            },
            "tempMin": {
                "name": "最低温度",
                "icon": "mdi:thermometer-minus",
                "unit": "°C",
                "device_class": "temperature"
            },
            "tempMax": {
                "name": "最高温度",
                "icon": "mdi:thermometer-plus",
                "unit": "°C",
                "device_class": "temperature"
            },
            "update_time": {
                "name": "更新时间",
                "icon": "mdi:clock-outline"
            }
        }
        
        today_extra_attrs = {
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
            },
            "fxDate": {
                "name": "预报日期",
                "icon": "mdi:calendar"
            },
            "sunrise": {
                "name": "日出时间",
                "icon": "mdi:weather-sunset-up"
            },
            "sunset": {
                "name": "日落时间",
                "icon": "mdi:weather-sunset-down"
            }
        }
        
        return {**base_attrs, **today_extra_attrs}

    def _validate_url(self, url: str) -> bool:
        """验证URL合法性"""
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ("http", "https"),
                parsed.path.startswith("/v7/weather/")
            ])
        except Exception:
            return False

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求的 URL、参数和请求头"""
        url = params["url"].strip()
        if not self._validate_url(url):
            raise ValueError(f"无效的API地址: {url}")
    
        request_params = {
            "location": params["location"],
            "key": params["api_key"],
            "lang": "zh",
            "unit": "m"
        }
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        return url, request_params, headers

    def parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强版响应解析"""
        try:
            if isinstance(response_data, str):
                response_data = json.loads(response_data)
                
            update_time = response_data.get("update_time", datetime.now().isoformat()) 
            
            # 检查顶层状态码
            if response_data.get("status") != "success":
                _LOGGER.error(f"API请求失败: {response_data.get('error', '未知错误')}")
                return {
                    "daily": [],
                    "api_source": "请求失败",
                    "update_time": update_time
                }
    
            # 获取天气数据
            data = response_data.get("data", {})
            if not data or "daily" not in data:
                _LOGGER.error(f"无效的API响应格式: {response_data}")
                return {
                    "daily": [],
                    #"api_source": "未知",
                    "update_time": update_time
                }
    
            daily_data = data["daily"]
            #api_source = data.get("fxLink", response_data.get("api_source", "未知"))
    
            return {
                "daily": daily_data,
                #"api_source": api_source,
                "update_time": update_time
            }
        except Exception as e:
            _LOGGER.error(f"解析响应数据时出错: {str(e)}")
            return {
                "daily": [],
                #"api_source": "解析错误",
                "update_time": update_time
            }

    def _get_day_data(self, forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天数据"""
        try:
            return forecast[index]
        except (IndexError, TypeError):
            return None

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """优化天气信息显示"""
        if not data or data.get("status") != "success":
            return "⏳ 获取天气中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"
        
        daily_data = data.get("data", {}).get("daily", [])
        if not daily_data:
            return "⚠️ 无有效天气数据"
        
        day_index = sensor_config.get("day_index", 0)
        day_data = self._get_day_data(daily_data, day_index)
        if not day_data:
            return "⚠️ 无指定日期的数据"
        
        # 核心天气信息
        return (
            f"☁ {day_data.get('textDay', '未知')}/{day_data.get('textNight', '未知')} "
            f"🌡 {day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C"
        )

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气传感器的完整属性"""
        if not data or data.get("status") != "success":
            return {}
        
        try:
            # 获取解析后的天气数据
            parsed_data = self.parse_response(data)
            daily_data = parsed_data.get("daily", [])
            day_index = sensor_config.get("day_index", 0)
            day_data = self._get_day_data(daily_data, day_index)
            
            if not day_data:
                return {}
            
            # 基础属性（所有日期都有的）
            base_attributes = {
                "textDay": day_data.get("textDay"),
                "textNight": day_data.get("textNight"),
                "tempMin": day_data.get("tempMin"),
                "tempMax": day_data.get("tempMax"),
                "api_source": parsed_data.get("api_source", "未知"),
                "update_time": parsed_data.get("update_time")
            }
            
            # 今天额外添加详细属性
            if day_index == 0:
                base_attributes.update({
                    "windDirDay": day_data.get("windDirDay"),
                    "windScaleDay": day_data.get("windScaleDay"),
                    "windSpeedDay": day_data.get("windSpeedDay"),
                    "windDirNight": day_data.get("windDirNight"),
                    "windScaleNight": day_data.get("windScaleNight"),
                    "windSpeedNight": day_data.get("windSpeedNight"),
                    "precip": day_data.get("precip"),
                    "uvIndex": day_data.get("uvIndex"),
                    "humidity": day_data.get("humidity"),
                    "pressure": day_data.get("pressure"),
                    "vis": day_data.get("vis"),
                    "cloud": day_data.get("cloud"),
                    "fxDate": day_data.get("fxDate"),
                    "sunrise": day_data.get("sunrise"),
                    "sunset": day_data.get("sunset")
                })
            
            # 调用父类方法处理通用属性
            return super().get_sensor_attributes(base_attributes, sensor_config)
            
        except Exception as e:
            _LOGGER.error(f"获取天气属性时出错: {str(e)}", exc_info=True)
            return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """3天预报传感器配置"""
        return [{
            "key": f"day_{i}",
            "name": f"{self.name} {['今天','明天','后天'][i]}",
            "icon": ["mdi:calendar-today", "mdi:calendar-arrow-right", "mdi:calendar-end"][i],
            "day_index": i,
            "device_class": "weather"
        } for i in range(3)]