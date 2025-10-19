from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"
        
class WeatherService(BaseService):
    """修复版每日天气服务"""

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
        """修复版响应数据解析 - 适配和风天气API格式"""
        try:
            _LOGGER.debug(f"开始解析天气响应数据: {type(response_data)}")
            
            # 处理协调器返回的数据结构
            if isinstance(response_data, dict) and "data" in response_data:
                # 这是协调器包装后的数据结构
                raw_data = response_data["data"]
                update_time = response_data.get("update_time", datetime.now().isoformat())
                status = response_data.get("status", "success")
            else:
                # 这是原始API响应
                raw_data = response_data
                update_time = datetime.now().isoformat()
                status = "success"

            # 如果已经是错误状态，直接返回
            if status != "success":
                return self._create_error_response(update_time)

            # 检查API响应状态
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    _LOGGER.error("无法解析JSON响应")
                    return self._create_error_response(update_time)

            # 和风天气API返回码检查
            code = raw_data.get("code")
            if code != "200":
                _LOGGER.error(f"和风天气API错误: {raw_data.get('code')} - {raw_data.get('message', '未知错误')}")
                return self._create_error_response(update_time)

            # 获取天气数据
            daily_data = raw_data.get("daily", [])
            if not daily_data:
                _LOGGER.error("API响应中缺少daily数据")
                return self._create_error_response(update_time)

            # 构建标准化数据字典
            result = {
                "daily": daily_data,
                "location_name": "当前城市",  # 和风天气3天预报API不返回城市名，需要单独获取
                "update_time": update_time,
                "status": "success"
            }

            # 提取今日、明日、后天的关键数据
            if len(daily_data) >= 1:
                today = daily_data[0]
                result.update({
                    "today_temp": f"{today.get('tempMin', '')}~{today.get('tempMax', '')}",
                    "today_weather": f"{today.get('textDay', '')}转{today.get('textNight', '')}",
                    "today_wind": today.get('windScaleDay', '')
                })

            if len(daily_data) >= 2:
                tomorrow = daily_data[1]
                result.update({
                    "tomorrow_temp": f"{tomorrow.get('tempMin', '')}~{tomorrow.get('tempMax', '')}",
                    "tomorrow_weather": f"{tomorrow.get('textDay', '')}转{tomorrow.get('textNight', '')}"
                })

            if len(daily_data) >= 3:
                day3 = daily_data[2]
                result.update({
                    "day3_temp": f"{day3.get('tempMin', '')}~{day3.get('tempMax', '')}",
                    "day3_weather": f"{day3.get('textDay', '')}转{day3.get('textNight', '')}"
                })

            # 构建天气趋势
            if len(daily_data) >= 3:
                trend_parts = []
                for i, day_data in enumerate(daily_data[:3]):
                    day_names = ["今天", "明天", "后天"]
                    temp_min = day_data.get('tempMin', '')
                    temp_max = day_data.get('tempMax', '')
                    weather_day = day_data.get('textDay', '')
                    
                    if temp_min and temp_max and weather_day:
                        trend_parts.append(
                            f"{day_names[i]}:{weather_day},{temp_min}~{temp_max}°C"
                        )
                result["trend"] = " | ".join(trend_parts) if trend_parts else "暂无趋势数据"

            _LOGGER.debug(f"解析后的天气数据: { {k: v for k, v in result.items() if k != 'daily'} }")
            return result

        except Exception as e:
            _LOGGER.error(f"解析响应数据时出错: {str(e)}", exc_info=True)
            return self._create_error_response(datetime.now().isoformat())

    def _create_error_response(self, update_time: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "daily": [],
            "location_name": "未知城市",
            "today_temp": "",
            "today_weather": "",
            "today_wind": "",
            "tomorrow_temp": "", 
            "tomorrow_weather": "",
            "day3_temp": "",
            "day3_weather": "",
            "trend": "暂无数据",
            "update_time": update_time,
            "status": "error"
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        if not data or data.get("status") != "success":
            return "数据加载中..." if data is None else "服务暂不可用"
            
        value = self.get_sensor_value(sensor_key, data)
        
        if not value:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key == "today_temp":
            return value if "~" in value and value.replace("~", "") else "暂无温度数据"
        elif sensor_key == "today_weather":
            return value if "转" in value and value.replace("转", "") else "暂无天气数据"
        elif sensor_key == "today_wind":
            return f"{value}级" if value else "未知风力"
        elif sensor_key == "tomorrow_temp":
            return value if "~" in value and value.replace("~", "") else "暂无温度数据"
        elif sensor_key == "tomorrow_weather":
            return value if "转" in value and value.replace("转", "") else "暂无天气数据"
        elif sensor_key == "day3_temp":
            return value if "~" in value and value.replace("~", "") else "暂无温度数据"
        elif sensor_key == "day3_weather":
            return value if "转" in value and value.replace("转", "") else "暂无天气数据"
        elif sensor_key == "trend":
            return value if value and value != "暂无趋势数据" else "暂无趋势数据"
        elif sensor_key == "location_name":
            return value if value and value != "未知城市" else "当前城市"
        else:
            return str(value) if value else "暂无数据"