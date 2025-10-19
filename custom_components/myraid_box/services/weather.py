from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"
        
class WeatherService(BaseService):
    """多传感器版每日天气服务"""

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
        """解析响应数据为标准化字典"""
        try:
            if isinstance(response_data, str):
                response_data = json.loads(response_data)

            update_time = response_data.get("update_time", datetime.now().isoformat())

            # 检查顶层状态码
            if response_data.get("status") != "success":
                _LOGGER.error(f"API请求失败: {response_data.get('error', '未知错误')}")
                return {
                    "daily": [],
                    "location_name": "未知",
                    "update_time": update_time
                }

            # 获取天气数据
            data = response_data.get("data", {})
            if not data or "daily" not in data:
                _LOGGER.error(f"无效的API响应格式: {response_data}")
                return {
                    "daily": [],
                    "location_name": "未知",
                    "update_time": update_time
                }

            daily_data = data["daily"]
            location_name = data.get("location_name", "未知城市")

            # 构建标准化数据字典
            result = {
                "daily": daily_data,
                "location_name": location_name,
                "update_time": update_time
            }

            # 提取今日、明日、后天的关键数据
            if len(daily_data) >= 1:
                today = daily_data[0]
                result.update({
                    "today_temp": f"{today.get('tempMin')}~{today.get('tempMax')}",
                    "today_weather": f"{today.get('textDay')}转{today.get('textNight')}",
                    "today_wind": today.get('windScaleDay', '未知')
                })

            if len(daily_data) >= 2:
                tomorrow = daily_data[1]
                result.update({
                    "tomorrow_temp": f"{tomorrow.get('tempMin')}~{tomorrow.get('tempMax')}",
                    "tomorrow_weather": f"{tomorrow.get('textDay')}转{tomorrow.get('textNight')}"
                })

            if len(daily_data) >= 3:
                day3 = daily_data[2]
                result.update({
                    "day3_temp": f"{day3.get('tempMin')}~{day3.get('tempMax')}",
                    "day3_weather": f"{day3.get('textDay')}转{day3.get('textNight')}"
                })

            # 构建天气趋势
            if len(daily_data) >= 3:
                trend_parts = []
                for i, day_data in enumerate(daily_data[:3]):
                    day_names = ["今天", "明天", "后天"]
                    trend_parts.append(
                        f"{day_names[i]}:{day_data.get('textDay', '未知')},"
                        f"{day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C"
                    )
                result["trend"] = " | ".join(trend_parts)

            return result

        except Exception as e:
            _LOGGER.error(f"解析响应数据时出错: {str(e)}")
            return {
                "daily": [],
                "location_name": "未知",
                "update_time": update_time
            }

    def _get_day_data(self, forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天数据"""
        try:
            return forecast[index]
        except (IndexError, TypeError):
            return None

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key == "today_temp":
            return value if value and "~" in value else "暂无温度数据"
        elif sensor_key == "today_weather":
            return value if value and "转" in value else "暂无天气数据"
        elif sensor_key == "today_wind":
            return f"{value}级" if value and value != "未知" else "未知风力"
        elif sensor_key == "tomorrow_temp":
            return value if value and "~" in value else "暂无温度数据"
        elif sensor_key == "tomorrow_weather":
            return value if value and "转" in value else "暂无天气数据"
        elif sensor_key == "day3_temp":
            return value if value and "~" in value else "暂无温度数据"
        elif sensor_key == "day3_weather":
            return value if value and "转" in value else "暂无天气数据"
        elif sensor_key == "trend":
            return value if value else "暂无趋势数据"
        elif sensor_key == "location_name":
            return value if value and value != "未知" else "未知城市"
        else:
            return str(value)