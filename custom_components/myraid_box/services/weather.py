from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"
        
class WeatherService(BaseService):
    """完全重写的每日天气服务"""

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
    def sensor_configs(self) -> List[SensorConfig]:
        """返回每日天气的所有传感器配置"""
        return [
            # 今日天气
            {
                "key": "today_temp",
                "name": "今日温度",
                "icon": "mdi:thermometer",
                "unit": "°C",
                "device_class": "temperature"
            },
            {
                "key": "today_weather",
                "name": "今日天气",
                "icon": "mdi:weather-partly-cloudy",
                "device_class": None
            },
            {
                "key": "today_wind",
                "name": "今日风力",
                "icon": "mdi:weather-windy",
                "unit": "级",
                "device_class": None
            },
            # 明日天气
            {
                "key": "tomorrow_temp",
                "name": "明日温度",
                "icon": "mdi:thermometer",
                "unit": "°C",
                "device_class": "temperature"
            },
            {
                "key": "tomorrow_weather",
                "name": "明日天气",
                "icon": "mdi:weather-partly-cloudy",
                "device_class": None
            },
            # 后天天气
            {
                "key": "day3_temp",
                "name": "后天温度",
                "icon": "mdi:thermometer",
                "unit": "°C",
                "device_class": "temperature"
            },
            {
                "key": "day3_weather",
                "name": "后天天气",
                "icon": "mdi:weather-partly-cloudy",
                "device_class": None
            },
            # 综合信息
            {
                "key": "trend",
                "name": "天气趋势",
                "icon": "mdi:chart-line",
                "device_class": None
            },
            {
                "key": "location_name",
                "name": "城市名称",
                "icon": "mdi:map-marker",
                "device_class": None
            }
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求的 URL、参数和请求头"""
        base_url = params["url"].strip()
        request_params = {
            "location": params["location"],
            "key": params["api_key"],
            "lang": "zh",
            "unit": "m"
        }
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        return base_url, request_params, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据 - 简化版本"""
        _LOGGER.debug(f"开始解析天气响应数据，类型: {type(response_data)}")
        
        # 如果是协调器返回的数据结构
        if isinstance(response_data, dict) and "data" in response_data:
            api_data = response_data["data"]
            status = response_data.get("status", "success")
            update_time = response_data.get("update_time", datetime.now().isoformat())
        else:
            api_data = response_data
            status = "success"
            update_time = datetime.now().isoformat()

        # 如果状态不是success，直接返回错误
        if status != "success":
            _LOGGER.error(f"天气服务状态错误: {status}")
            return self._create_empty_data(update_time)

        try:
            # 如果api_data是字符串，尝试解析JSON
            if isinstance(api_data, str):
                api_data = json.loads(api_data)

            # 检查API返回码
            if isinstance(api_data, dict) and api_data.get("code") != "200":
                _LOGGER.error(f"和风天气API错误: {api_data.get('code')} - {api_data.get('message')}")
                return self._create_empty_data(update_time)

            # 获取daily数据
            daily_data = api_data.get("daily", []) if isinstance(api_data, dict) else []
            
            if not daily_data:
                _LOGGER.error("未找到天气数据")
                return self._create_empty_data(update_time)

            # 构建结果
            result = {
                "status": "success",
                "update_time": update_time,
                "location_name": "当前城市"
            }

            # 处理今天的数据
            if len(daily_data) > 0:
                today = daily_data[0]
                result["today_temp"] = f"{today.get('tempMin', '')}~{today.get('tempMax', '')}"
                result["today_weather"] = f"{today.get('textDay', '')}转{today.get('textNight', '')}"
                result["today_wind"] = today.get('windScaleDay', '')

            # 处理明天的数据
            if len(daily_data) > 1:
                tomorrow = daily_data[1]
                result["tomorrow_temp"] = f"{tomorrow.get('tempMin', '')}~{tomorrow.get('tempMax', '')}"
                result["tomorrow_weather"] = f"{tomorrow.get('textDay', '')}转{tomorrow.get('textNight', '')}"

            # 处理后天的数据
            if len(daily_data) > 2:
                day3 = daily_data[2]
                result["day3_temp"] = f"{day3.get('tempMin', '')}~{day3.get('tempMax', '')}"
                result["day3_weather"] = f"{day3.get('textDay', '')}转{day3.get('textNight', '')}"

            # 构建趋势
            if len(daily_data) >= 3:
                trends = []
                day_names = ["今天", "明天", "后天"]
                for i in range(3):
                    day = daily_data[i]
                    temp_min = day.get('tempMin', '')
                    temp_max = day.get('tempMax', '')
                    weather = day.get('textDay', '')
                    if temp_min and temp_max and weather:
                        trends.append(f"{day_names[i]}:{weather},{temp_min}~{temp_max}°C")
                result["trend"] = " | ".join(trends) if trends else "暂无趋势数据"

            _LOGGER.debug(f"解析成功: {result}")
            return result

        except Exception as e:
            _LOGGER.error(f"解析天气数据时出错: {str(e)}", exc_info=True)
            return self._create_empty_data(update_time)

    def _create_empty_data(self, update_time: str) -> Dict[str, Any]:
        """创建空数据响应"""
        return {
            "status": "error",
            "update_time": update_time,
            "location_name": "未知城市",
            "today_temp": "",
            "today_weather": "",
            "today_wind": "",
            "tomorrow_temp": "",
            "tomorrow_weather": "",
            "day3_temp": "",
            "day3_weather": "",
            "trend": "暂无数据"
        }

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """重写获取传感器值方法"""
        if not data or data.get("status") != "success":
            return None
        return data.get(sensor_key)

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "数据加载中..."
            
        if not value:
            return "暂无数据"
            
        # 特殊处理各个传感器
        if sensor_key.endswith("_temp"):
            if "~" in value and value.replace("~", "").strip():
                return value
            return "暂无温度数据"
            
        elif sensor_key.endswith("_weather"):
            if "转" in value and value.replace("转", "").strip():
                return value
            return "暂无天气数据"
            
        elif sensor_key == "today_wind":
            return f"{value}级" if value else "未知风力"
            
        elif sensor_key == "trend":
            return value if value and value != "暂无趋势数据" else "暂无趋势数据"
            
        elif sensor_key == "location_name":
            return value if value else "未知城市"
            
        return str(value) if value else "暂无数据"