from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
from urllib.parse import urlparse
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_WEATHER_API = "https://devapi.qweather.com/v7/weather/3d"
        
class WeatherService(BaseService):
    """包含降水信息的天气服务"""

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
        """包含降水信息的传感器配置"""
        return [
            # 今日关键信息
            {
                "key": "weather_condition",
                "name": "今天",
                "icon": "mdi:weather-partly-cloudy",
                "device_class": None
            },
            {
                "key": "temperature", 
                "name": "温度",
                "icon": "mdi:thermometer",
                "device_class": None
            },
            {
                "key": "humidity",
                "name": "湿度",
                "icon": "mdi:water-percent",
                "unit": "%", 
                "device_class": "humidity"
            },
            {
                "key": "wind",
                "name": "风力", 
                "icon": "mdi:weather-windy",
                "device_class": None
            },
            {
                "key": "uv_index",
                "name": "紫外线",
                "icon": "mdi:weather-sunny-alert",
                "device_class": None
            },
            {
                "key": "precipitation",
                "name": "降水概率",
                "icon": "mdi:weather-rainy",
                "device_class": None
            },
            # 未来预报
            {
                "key": "tomorrow",
                "name": "明天",
                "icon": "mdi:weather-partly-cloudy",
                "device_class": None
            },
            {
                "key": "day_after_tomorrow",
                "name": "后天",
                "icon": "mdi:weather-cloudy",
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
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "application/json"
        }
        return url, request_params, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据"""
        try:
            # 第一层：协调器包装的数据
            if isinstance(response_data, dict) and "data" in response_data:
                api_response = response_data["data"]
                update_time = response_data.get("update_time", datetime.now().isoformat())
                status = response_data.get("status", "success")
            else:
                api_response = response_data
                update_time = datetime.now().isoformat()
                status = "success"

            if status != "success":
                return {
                    "status": "error",
                    "error": "API请求失败",
                    "update_time": update_time
                }

            # 如果api_response是字符串，尝试解析JSON
            if isinstance(api_response, str):
                try:
                    api_response = json.loads(api_response)
                except json.JSONDecodeError as e:
                    return {
                        "status": "error", 
                        "error": f"JSON解析失败: {e}",
                        "update_time": update_time
                    }

            # 检查和风天气API返回码
            code = api_response.get("code")
            if code != "200":
                return {
                    "status": "error",
                    "error": f"API错误: {api_response.get('message', '未知错误')}",
                    "update_time": update_time
                }

            # 获取天气数据
            daily_data = api_response.get("daily", [])
            if not daily_data:
                return {
                    "status": "error",
                    "error": "未找到天气数据",
                    "update_time": update_time
                }

            # 返回协调器期望的数据结构
            return {
                "status": "success",
                "data": {
                    "daily": daily_data,
                    "api_source": api_response.get("fxLink", "未知")
                },
                "update_time": update_time
            }

        except Exception as e:
            return {
                "status": "error",
                "error": f"解析错误: {str(e)}",
                "update_time": datetime.now().isoformat()
            }

    def _get_day_data(self, forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天数据"""
        try:
            return forecast[index]
        except (IndexError, TypeError):
            return None

    def _has_rain_today(self, today_data: Dict) -> str:
        """判断今日是否有雨"""
        if not today_data:
            return "未知"
            
        text_day = today_data.get('textDay', '')
        text_night = today_data.get('textNight', '')
        precip = float(today_data.get('precip', 0))
        
        # 根据天气描述判断
        rain_keywords = ['雨', '雪', '雹']
        has_rain_by_text = any(keyword in text_day for keyword in rain_keywords) or any(keyword in text_night for keyword in rain_keywords)
        
        # 根据降水量判断
        has_rain_by_precip = precip > 0
        
        if has_rain_by_text or has_rain_by_precip:
            rain_times = []
            if any(keyword in text_day for keyword in rain_keywords):
                rain_times.append("白天")
            if any(keyword in text_night for keyword in rain_keywords):
                rain_times.append("夜间")
            return f"{'、'.join(rain_times)}有雨"
        else:
            return "无雨"

    def _get_rain_forecast(self, daily_data: List[Dict]) -> str:
        """获取三日降水预报"""
        rain_forecast = []
        day_names = ["今天", "明天", "后天"]
        
        for i in range(3):
            day_data = self._get_day_data(daily_data, i)
            if day_data:
                text_day = day_data.get('textDay', '')
                text_night = day_data.get('textNight', '')
                precip = day_data.get('precip', '0')
                
                rain_keywords = ['雨', '雪', '雹']
                has_rain = any(keyword in text_day for keyword in rain_keywords) or any(keyword in text_night for keyword in rain_keywords)
                
                if has_rain:
                    rain_types = []
                    if any(keyword in text_day for keyword in rain_keywords):
                        rain_types.append(f"白天{text_day}")
                    if any(keyword in text_night for keyword in rain_keywords):
                        rain_types.append(f"夜间{text_night}")
                    rain_forecast.append(f"{day_names[i]}{''.join(rain_types)}")
        
        if rain_forecast:
            return "；".join(rain_forecast)
        else:
            return "未来三天无雨"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据不同传感器key返回对应值"""
        if not data or data.get("status") != "success":
            return None if sensor_key == "humidity" else "数据加载中"
            
        data_content = data.get("data", {})
        daily_data = data_content.get("daily", [])
        
        if not daily_data:
            return None if sensor_key == "humidity" else "无数据"
            
        today_data = self._get_day_data(daily_data, 0)
        tomorrow_data = self._get_day_data(daily_data, 1)
        day3_data = self._get_day_data(daily_data, 2)
        
        if sensor_key == "weather_condition":
            if today_data:
                return f"白天{today_data.get('textDay', '未知')},夜间{today_data.get('textNight', '未知')}"
            return "未知"
            
        elif sensor_key == "temperature":
            if today_data:
                return f"{today_data.get('tempMin', 'N/A')}-{today_data.get('tempMax', 'N/A')}℃"
            return "未知"
            
        elif sensor_key == "humidity":
            if today_data:
                humidity = today_data.get('humidity')
                try:
                    return int(humidity) if humidity and humidity != '未知' else None
                except (ValueError, TypeError):
                    return None
            return None
            
        elif sensor_key == "wind":
            if today_data:
                return f"{today_data.get('windDirDay', '未知')}{today_data.get('windScaleDay', '未知')}级"
            return "未知"
            
        elif sensor_key == "uv_index":
            if today_data:
                uv_index = today_data.get('uvIndex', '未知')
                return f"{uv_index}级" if uv_index != '未知' else "未知"
            return "未知"
            
        elif sensor_key == "precipitation":
            if today_data:
                return self._has_rain_today(today_data)
            return "未知"
            
        elif sensor_key == "tomorrow":
            if tomorrow_data:
                return f"白天{tomorrow_data.get('textDay', '未知')},夜间{tomorrow_data.get('textNight', '未知')}，温度 {tomorrow_data.get('tempMin', 'N/A')}-{tomorrow_data.get('tempMax', 'N/A')}℃"
            return "未知"
            
        elif sensor_key == "day_after_tomorrow":
            if day3_data:
                return f"白天{day3_data.get('textDay', '未知')},夜间{day3_data.get('textNight', '未知')}，温度 {day3_data.get('tempMin', 'N/A')}-{day3_data.get('tempMax', 'N/A')}℃"
            return "未知"
        
        return "未知传感器"

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data or data.get("status") != "success":
            return {}
    
        try:
            data_content = data.get("data", {})
            daily_data = data_content.get("daily", [])
            attributes = {
                "数据来源": data_content.get("api_source", "未知"),
                "更新时间": data.get("update_time", "未知")
            }
    
            # 为今天相关的传感器添加详细属性
            if sensor_key in ["weather_condition", "temperature", "humidity", "wind", "uv_index", "precipitation"]:
                today_data = self._get_day_data(daily_data, 0)
                if today_data:
                    attributes.update({
                        "日出时间": today_data.get('sunrise', '未知'),
                        "日落时间": today_data.get('sunset', '未知'),
                        "今日降水量": f"{today_data.get('precip', '未知')}mm",
                        "气压": f"{today_data.get('pressure', '未知')}hPa",
                        "能见度": f"{today_data.get('vis', '未知')}km",
                        "三日降水预报": self._get_rain_forecast(daily_data)
                    })
            # 为明天传感器添加属性
            elif sensor_key == "tomorrow":
                tomorrow_data = self._get_day_data(daily_data, 1)
                if tomorrow_data:
                    attributes.update({
                        "日出时间": tomorrow_data.get('sunrise', '未知'),
                        "日落时间": tomorrow_data.get('sunset', '未知'),
                        "明日降水量": f"{tomorrow_data.get('precip', '未知')}mm"
                    })
            # 为后天传感器添加属性
            elif sensor_key == "day_after_tomorrow":
                day3_data = self._get_day_data(daily_data, 2)
                if day3_data:
                    attributes.update({
                        "日出时间": day3_data.get('sunrise', '未知'),
                        "日落时间": day3_data.get('sunset', '未知'),
                        "后日降水量": f"{day3_data.get('precip', '未知')}mm"
                    })
    
            return attributes
    
        except Exception as e:
            return {}