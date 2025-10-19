from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"
        
class WeatherService(BaseService):
    """完全修复的每日天气服务"""

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
        """返回每日天气的所有传感器配置 - 移除温度传感器的单位"""
        return [
            # 今日天气
            {
                "key": "today_temp",
                "name": "今日温度",
                "icon": "mdi:thermometer",
                "unit": None,  # 移除单位，避免被识别为数值传感器
                "device_class": None
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
                "unit": None,  # 移除单位
                "device_class": None
            },
            # 明日天气
            {
                "key": "tomorrow_temp",
                "name": "明日温度",
                "icon": "mdi:thermometer",
                "unit": None,  # 移除单位
                "device_class": None
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
                "unit": None,  # 移除单位
                "device_class": None
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
        url = params["url"].strip()
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

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据"""
        try:
            _LOGGER.debug(f"开始解析天气响应数据，类型: {type(response_data)}")
            
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

            # 如果状态不是success，直接返回错误
            if status != "success":
                _LOGGER.error(f"天气服务状态错误: {status}")
                return self._create_empty_data(update_time)

            # 如果raw_data是字符串，尝试解析JSON
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)

            # 检查和风天气API返回码
            code = raw_data.get("code")
            if code != "200":
                _LOGGER.error(f"和风天气API错误: {raw_data.get('code')} - {raw_data.get('message', '未知错误')}")
                return self._create_empty_data(update_time)

            # 获取天气数据
            daily_data = raw_data.get("daily", [])
            if not daily_data:
                _LOGGER.error("未找到天气数据")
                return self._create_empty_data(update_time)

            # 构建标准化数据字典
            result = {
                "status": "success",
                "update_time": update_time,
                "location_name": "当前城市",
                "daily": daily_data,
                "api_source": raw_data.get("fxLink", "未知")
            }

            # 提取今日、明日、后天的关键数据
            if len(daily_data) >= 1:
                today = daily_data[0]
                result.update({
                    "today_temp": f"{today.get('tempMin', '')}~{today.get('tempMax', '')}°C",  # 在值中包含单位
                    "today_weather": f"{today.get('textDay', '')}转{today.get('textNight', '')}",
                    "today_wind": f"{today.get('windScaleDay', '')}级"  # 在值中包含单位
                })

            if len(daily_data) >= 2:
                tomorrow = daily_data[1]
                result.update({
                    "tomorrow_temp": f"{tomorrow.get('tempMin', '')}~{tomorrow.get('tempMax', '')}°C",
                    "tomorrow_weather": f"{tomorrow.get('textDay', '')}转{tomorrow.get('textNight', '')}"
                })

            if len(daily_data) >= 3:
                day3 = daily_data[2]
                result.update({
                    "day3_temp": f"{day3.get('tempMin', '')}~{day3.get('tempMax', '')}°C",
                    "day3_weather": f"{day3.get('textDay', '')}转{day3.get('textNight', '')}"
                })

            # 构建天气趋势
            if len(daily_data) >= 3:
                trend = []
                for i in range(3):
                    day_data = daily_data[i]
                    if day_data:
                        trend.append(
                            f"{['今天', '明天', '后天'][i]}："
                            f"白天{day_data.get('textDay', '未知')}, "
                            f"夜间{day_data.get('textNight', '未知')}, "
                            f"{day_data.get('tempMin', 'N/A')}~{day_data.get('tempMax', 'N/A')}°C"
                        )
                result["trend"] = "；".join(trend)

            _LOGGER.debug(f"解析成功: { {k: v for k, v in result.items() if k != 'daily'} }")
            return result

        except Exception as e:
            _LOGGER.error(f"解析天气数据时出错: {str(e)}")
            return self._create_empty_data(datetime.now().isoformat())

    def _create_empty_data(self, update_time: str) -> Dict[str, Any]:
        """创建空数据响应"""
        return {
            "status": "error",
            "update_time": update_time,
            "location_name": "未知城市",
            "today_temp": "暂无温度数据",
            "today_weather": "暂无天气数据",
            "today_wind": "未知风力",
            "tomorrow_temp": "暂无温度数据",
            "tomorrow_weather": "暂无天气数据",
            "day3_temp": "暂无温度数据",
            "day3_weather": "暂无天气数据",
            "trend": "暂无趋势数据",
            "daily": [],
            "api_source": "未知"
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器值 - 确保所有传感器都返回有效字符串"""
        if not data or data.get("status") != "success":
            # 返回有效的字符串，避免数值转换错误
            return "数据加载中"
            
        value = data.get(sensor_key)
        
        if not value:
            # 返回有效的默认字符串
            if sensor_key.endswith("_temp"):
                return "暂无温度数据"
            elif sensor_key.endswith("_weather"):
                return "暂无天气数据"
            elif sensor_key == "today_wind":
                return "未知风力"
            elif sensor_key == "trend":
                return "暂无趋势数据"
            elif sensor_key == "location_name":
                return "未知城市"
            else:
                return "暂无数据"
                
        return str(value)