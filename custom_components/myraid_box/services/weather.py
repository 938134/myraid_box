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
    def attributes(self) -> Dict[str, Dict[str, Any]]:
        return {
            "sunrise": {
                "name": "🌅 日出时间",
                "icon": "mdi:weather-sunset-up"
            },
            "sunset": {
                "name": "🌇 日落时间",
                "icon": "mdi:weather-sunset-down"
            },
            "textDay": {
                "name": "🌞 白天天气",
                "icon": "mdi:weather-sunny"
            },
            "textNight": {
                "name": "🌙 夜间天气",
                "icon": "mdi:weather-night"
            },
            "tempMin": {
                "name": "🌡 最低温度",
                "icon": "mdi:thermometer-minus",
                "unit": "°C",
                "device_class": "temperature"
            },
            "tempMax": {
                "name": "🌡 最高温度",
                "icon": "mdi:thermometer-plus",
                "unit": "°C",
                "device_class": "temperature"
            },
            "windDirDay": {
                "name": "💨 白天风向",
                "icon": "mdi:weather-windy"
            },
            "windScaleDay": {
                "name": "🌬 白天风力",
                "icon": "mdi:weather-windy",
                "unit": "级"
            },
            "windSpeedDay": {
                "name": "💨 白天风速",
                "icon": "mdi:weather-windy",
                "unit": "km/h"
            },
            "windDirNight": {
                "name": "💨 夜间风向",
                "icon": "mdi:weather-windy"
            },
            "windScaleNight": {
                "name": "🌬 夜间风力",
                "icon": "mdi:weather-windy",
                "unit": "级"
            },
            "windSpeedNight": {
                "name": "💨 夜间风速",
                "icon": "mdi:weather-windy",
                "unit": "km/h"
            },
            "precip": {
                "name": "🌧 降水量",
                "icon": "mdi:weather-rainy",
                "unit": "mm"
            },
            "uvIndex": {
                "name": "☀️ 紫外线指数",
                "icon": "mdi:weather-sunny-alert"
            },
            "humidity": {
                "name": "💧 湿度",
                "icon": "mdi:water-percent",
                "unit": "%"
            },
            "pressure": {
                "name": "📊 大气压",
                "icon": "mdi:gauge",
                "unit": "hPa"
            },
            "vis": {
                "name": "👀 能见度",
                "icon": "mdi:eye",
                "unit": "km"
            },
            "cloud": {
                "name": "☁️ 云量",
                "icon": "mdi:weather-cloudy",
                "unit": "%"
            },
            "update_time": {
                "name": "⏱ 更新时间",
                "icon": "mdi:clock-outline"
            }
        }

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
                    "api_source": "未知",
                    "update_time": update_time
                }

            daily_data = data["daily"]
            api_source = data.get("fxLink", response_data.get("api_source", "未知"))

            return {
                "daily": daily_data,
                "api_source": api_source,
                "update_time": update_time
            }
        except Exception as e:
            _LOGGER.error(f"解析响应数据时出错: {str(e)}")
            return {
                "daily": [],
                "api_source": "解析错误",
                "update_time": update_time
            }

    def _get_day_data(self, forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天数据"""
        try:
            return forecast[index]
        except (IndexError, TypeError):
            return None

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """优化天气信息显示，使用 attributes 中定义的字段名称，去掉多余的图标引用"""
        if not data or data.get("status") != "success":
            return "⏳ 获取天气中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"

        daily_data = data.get("data", {}).get("daily", [])
        if not daily_data:
            return "⚠️ 无有效天气数据"

        if sensor_config.get("key") == "trend":
            trend = ""
            for i in range(3):
                day_data = self._get_day_data(daily_data, i)
                if day_data:
                    trend += f"{['今天', '明天', '后天'][i]}：🌞 白天{day_data.get('textDay', '未知')},🌙 夜间{day_data.get('textNight', '未知')},🌡温度{day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C;\n"

            return trend

        day_index = sensor_config.get("day_index", 0)
        day_data = self._get_day_data(daily_data, day_index)
        if not day_data:
            return "⚠️ 无指定日期的数据"

        state = (
            f"🌞 白天{day_data.get('textDay', '未知')},"
            f"🌙 夜间{day_data.get('textNight', '未知')},"
            f"🌡 温度{day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C"
        )

        # 确保状态字符串长度不超过 255 个字符
        if len(state) > 255:
            state = state[:252] + "..."

        return state

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

            # 为辅助传感器（trend）添加今日天气详情
            if sensor_config.get("key") == "trend":
                attributes = {
                    "天气详情": "\n".join([
                        f"🌅 日出时间 {day_data.get('sunrise', '未知')}",
                        f"🌇 日落时间 {day_data.get('sunset', '未知')}",
                        f"🌞 白天天气 {day_data.get('textDay', '未知')}",
                        f"🌙 夜间天气 {day_data.get('textNight', '未知')}",
                        f"🌡 最低温度 {day_data.get('tempMin', '未知')}°C",
                        f"🌡 最高温度 {day_data.get('tempMax', '未知')}°C",
                        f"💨 白天风向 {day_data.get('windDirDay', '未知')}",
                        f"🌬 白天风力 {day_data.get('windScaleDay', '未知')} 级",
                        f"💨 白天风速 {day_data.get('windSpeedDay', '未知')} km/h",
                        f"💨 夜间风向 {day_data.get('windDirNight', '未知')}",
                        f"🌬 夜间风力 {day_data.get('windScaleNight', '未知')} 级",
                        f"💨 夜间风速 {day_data.get('windSpeedNight', '未知')} km/h",
                        f"🌧 降水量 {day_data.get('precip', '未知')} mm",
                        f"☀️ 紫外线指数 {day_data.get('uvIndex', '未知')}",
                        f"💧 湿度 {day_data.get('humidity', '未知')}%",
                        f"📊 大气压 {day_data.get('pressure', '未知')} hPa",
                        f"👀 能见度 {day_data.get('vis', '未知')} km",
                        f"☁️ 云量 {day_data.get('cloud', '未知')}%"
                    ])
                }
                return attributes

            # 根据 attributes 定义动态生成属性值
            attributes = {}
            for attr_key, attr_config in self.attributes.items():
                value = day_data.get(attr_key)
                if value is not None:
                    attributes[attr_config["name"]] = value

            return attributes

        except Exception as e:
            _LOGGER.error(f"获取天气属性时出错: {str(e)}", exc_info=True)
            return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """3天预报传感器配置 + 辅助传感器"""
        return [
            {
                "key": f"day_{i}",
                "name": f"{['今天', '明天', '后天'][i]}",
                "icon": ["mdi:calendar-today", "mdi:calendar-arrow-right", "mdi:calendar-end"][i],
                "day_index": i,
                "device_class": f"{self.service_id}"
            } for i in range(3)
        ] + [
            {
                "key": "trend",
                "name": "天气趋势",
                "icon": "mdi:calendar-month",
                "device_class": f"{self.service_id}"
            }
        ]