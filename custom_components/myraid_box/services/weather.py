from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
import aiohttp
import time
import jwt
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class WeatherService(BaseService):
    """每日天气服务 - 使用新版基类"""

    DEFAULT_API_URL = "https://devapi.qweather.com"
    DEFAULT_UPDATE_INTERVAL = 30
    DEFAULT_TIMEOUT = 60  # 天气API可能较慢

    def __init__(self):
        super().__init__()
        self._current_city_id = None

    @property
    def service_id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "每日天气"

    @property
    def description(self) -> str:
        return "使用官方JWT认证获取3天天气预报"

    @property
    def config_help(self) -> str:
        return "🌤️ 天气服务配置说明：\n1. 注册和风天气开发者账号：https://dev.qweather.com/\n2. 创建项目获取项目ID、密钥ID和EdDSA私钥\n3. 城市名称支持中文、拼音或LocationID"

    @property
    def icon(self) -> str:
        return "mdi:weather-cloudy-clock"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "location": {
                "name": "城市名称",
                "type": "str",
                "default": "beij",
                "description": "城市名称或拼音（如：beij, shanghai）"
            },
            "api_host": {
                "name": "API主机",
                "type": "str",
                "default": "https://devapi.qweather.com",
                "description": "天气API服务地址"
            },
            "private_key": {
                "name": "私钥",
                "type": "password",
                "default": "",
                "description": "EdDSA私钥（PEM格式）"
            },
            "project_id": {
                "name": "项目ID",
                "type": "str",
                "default": "PROJECT_ID",
                "description": "项目标识符"
            },
            "key_id": {
                "name": "密钥ID",
                "type": "str",
                "default": "KEY_ID",
                "description": "密钥标识符"
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日天气服务的传感器配置"""
        return [
            # 城市信息
            self._create_sensor_config("city_name", "城市", "mdi:city"),
            # 今日天气
            self._create_sensor_config("today_weather", "今天", "mdi:weather-partly-cloudy"),
            self._create_sensor_config("today_temp", "温度", "mdi:thermometer"),
            self._create_sensor_config("today_humidity", "湿度", "mdi:water-percent", "%", "humidity"),
            self._create_sensor_config("today_wind", "风力", "mdi:weather-windy"),
            self._create_sensor_config("today_precip", "降水", "mdi:weather-rainy", "mm"),
            self._create_sensor_config("today_pressure", "气压", "mdi:gauge", "hPa"),
            self._create_sensor_config("today_vis", "能见度", "mdi:eye", "km"),
            self._create_sensor_config("today_cloud", "云量", "mdi:cloud", "%"),
            self._create_sensor_config("today_uv", "紫外线", "mdi:weather-sunny-alert"),
            # 未来天气
            self._create_sensor_config("tomorrow_weather", "明天", "mdi:weather-partly-cloudy"),
            self._create_sensor_config("day3_weather", "后天", "mdi:weather-cloudy"),
        ]

    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """生成和风天气JWT token"""
        if self._token and self._token_expiry and time.time() < self._token_expiry:
            return self._token
            
        private_key = params.get("private_key", "").strip()
        project_id = params.get("project_id", "YOUR_PROJECT_ID")
        key_id = params.get("key_id", "YOUR_KEY_ID")
        
        if not private_key:
            _LOGGER.error("天气服务私钥未配置")
            return ""
        
        payload = {
            'iat': int(time.time()) - 30,
            'exp': int(time.time()) + 900,  # 15分钟有效期
            'sub': project_id
        }
        
        try:
            self._token = jwt.encode(payload, private_key, algorithm='EdDSA', headers={'kid': key_id})
            self._token_expiry = payload['exp']
            _LOGGER.debug("成功生成天气JWT令牌")
            return self._token
        except Exception as e:
            _LOGGER.error("生成天气JWT令牌失败: %s", str(e))
            return ""

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建天气API请求 - 城市查询"""
        api_host = params.get("api_host", self.default_api_url).rstrip('/')
        location = params.get("location", "beij")
        
        url = f"{api_host}/geo/v2/city/lookup"
        
        return RequestConfig(
            url=url,
            method="GET",
            params={"location": location}
        )

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        """构建天气API认证头"""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据 - 重写以支持两步请求"""
        try:
            # 1. 获取城市信息
            city_result = await super().fetch_data(coordinator, params)
            
            if city_result.get("status") != "success":
                return city_result
            
            # 2. 从城市数据中提取城市ID并获取天气数据
            city_data = city_result.get("data", {})
            weather_data = await self._fetch_weather_data(params, city_data)
            
            return {
                "data": weather_data,
                "status": "success",
                "error": None,
                "update_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            _LOGGER.error("[天气服务] 获取天气数据失败: %s", str(e), exc_info=True)
            return self._create_error_response(str(e))

    async def _fetch_weather_data(self, params: Dict[str, Any], city_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据"""
        try:
            city_info = ((city_data.get("location", []) or [{}])[0])
            city_id = city_info.get("id")
            
            if not city_id:
                return self._create_weather_response(city_info, {}, "城市ID无效")
            
            api_host = params.get("api_host", self.default_api_url).rstrip('/')
            weather_url = f"{api_host}/v7/weather/3d"
            
            # 获取token
            token = await self._ensure_token(params)
            if not token:
                return self._create_weather_response(city_info, {}, "JWT令牌无效")
            
            # 构建天气请求头 - 使用基类的_build_auth_headers方法
            headers = self._build_auth_headers(token)
            
            async with self._session.get(
                weather_url, 
                params={"location": city_id}, 
                headers=headers
            ) as resp:
                if resp.status == 401:
                    return self._create_weather_response(city_info, {}, "天气API认证失败")
                
                resp.raise_for_status()
                weather_response = await resp.json()
                
                if weather_response.get("code") != "200":
                    error_msg = weather_response.get("message", "天气数据获取失败")
                    return self._create_weather_response(city_info, {}, f"天气API错误: {error_msg}")
                
                return self._create_weather_response(
                    city_info,
                    city_data.get("refer", {}),
                    "有效",
                    weather_data=weather_response,
                    daily_forecast=weather_response.get("daily", []),
                    weather_api=weather_response.get("refer", {}).get("sources", ["未知"])[0],
                    update_time=weather_response.get("updateTime", "未知")
                )
                
        except Exception as e:
            _LOGGER.error("[天气服务] 获取天气数据失败: %s", str(e))
            city_info = ((city_data.get("location", []) or [{}])[0])
            return self._create_weather_response(
                city_info, 
                city_data.get("refer", {}), 
                f"获取失败: {str(e)}"
            )
        
    def _create_weather_response(self, city_info: Dict, city_api: Dict, jwt_status: str, 
                               weather_data: Optional[Dict] = None, daily_forecast: List = None,
                               weather_api: str = "未知", update_time: str = "未知") -> Dict[str, Any]:
        """创建天气数据响应"""
        return {
            "city_info": city_info,
            "weather_data": weather_data or {},
            "daily_forecast": daily_forecast or [],
            "api_source": {
                "city_api": city_api.get("sources", ["未知"])[0],
                "weather_api": weather_api
            },
            "update_time": update_time,
            "jwt_status": jwt_status
        }

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析城市查询响应数据"""
        if not isinstance(response_data, dict):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        # 检查API返回码
        code = response_data.get("code")
        if code != "200":
            error_msg = response_data.get("message", "未知错误")
            return {
                "status": "error",
                "error": f"城市查询失败: {error_msg}"
            }

        return response_data

    def _get_day_forecast(self, daily_forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天预报数据"""
        try:
            if not daily_forecast or not isinstance(daily_forecast, list):
                return None
            return daily_forecast[index] if index < len(daily_forecast) else None
        except (IndexError, TypeError, AttributeError):
            return None

    def _format_temperature(self, temp_min: Any, temp_max: Any) -> str:
        """格式化温度显示"""
        try:
            if temp_min is None and temp_max is None:
                return "未知"
            
            min_temp = str(temp_min).strip() if temp_min is not None else ""
            max_temp = str(temp_max).strip() if temp_max is not None else ""
            
            if not min_temp and not max_temp:
                return "未知"
            if not min_temp:
                return f"{max_temp}°C"
            if not max_temp:
                return f"{min_temp}°C"
            
            return f"{min_temp}°C" if min_temp == max_temp else f"{min_temp}~{max_temp}°C"
                
        except Exception:
            return "未知"

    def _format_weather_text(self, weather_day: str, weather_night: str) -> str:
        """格式化天气文本"""
        if not weather_day or not weather_night:
            return weather_day or weather_night or "未知"
        
        if weather_day == weather_night:
            return weather_day
        
        return f"白天{weather_day}，夜间{weather_night}"

    def _format_wind_text(self, wind_dir_day: str, wind_scale_day: str, wind_dir_night: str, wind_scale_night: str) -> str:
        """格式化风力文本"""
        day_wind = f"{wind_dir_day}{wind_scale_day}级" if wind_dir_day and wind_scale_day else ""
        night_wind = f"{wind_dir_night}{wind_scale_night}级" if wind_dir_night and wind_scale_night else ""
        
        if not day_wind and not night_wind:
            return "未知"
        if not day_wind:
            return night_wind
        if not night_wind:
            return day_wind
        
        if day_wind == night_wind:
            return day_wind
        
        return f"白天{day_wind}，夜间{night_wind}"

    def _format_future_weather(self, weather_data: Optional[Dict]) -> str:
        """格式化未来天气信息"""
        if not weather_data:
            return "暂无数据"
        
        weather_text = self._format_weather_text(
            weather_data.get('textDay', ''), 
            weather_data.get('textNight', '')
        )
        temp_str = self._format_temperature(weather_data.get('tempMin'), weather_data.get('tempMax'))
        
        wind_text = self._format_wind_text(
            weather_data.get('windDirDay', ''), 
            weather_data.get('windScaleDay', ''),
            weather_data.get('windDirNight', ''),
            weather_data.get('windScaleNight', '')
        )
    
        return f"{weather_text}，{temp_str}，{wind_text}"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据不同传感器key返回对应值"""
        if not data or data.get("status") != "success":
            return self._get_sensor_default(sensor_key)
            
        data_content = data.get("data", {})
        city_info = data_content.get("city_info", {})
        daily_forecast = data_content.get("daily_forecast", [])
        
        # 获取预报数据
        forecast_data = {
            0: self._get_day_forecast(daily_forecast, 0),  # 今天
            1: self._get_day_forecast(daily_forecast, 1),  # 明天
            2: self._get_day_forecast(daily_forecast, 2),  # 后天
        }
        
        # 传感器值映射
        value_mapping = {
            # 城市信息
            "city_name": lambda: city_info.get("name", "未知"),
            
            # 今日天气
            "today_weather": lambda: self._format_weather_text(
                forecast_data[0].get('textDay', ''), 
                forecast_data[0].get('textNight', '')
            ) if forecast_data[0] else "暂无数据",
            
            "today_temp": lambda: self._format_temperature(
                forecast_data[0].get('tempMin'), 
                forecast_data[0].get('tempMax')
            ) if forecast_data[0] else "未知",
                
            "today_humidity": lambda: forecast_data[0].get('humidity') if forecast_data[0] else None,
            
            "today_wind": lambda: self._format_wind_text(
                forecast_data[0].get('windDirDay', ''), 
                forecast_data[0].get('windScaleDay', ''),
                forecast_data[0].get('windDirNight', ''),
                forecast_data[0].get('windScaleNight', '')
            ) if forecast_data[0] else "未知",
            
            "today_precip": lambda: forecast_data[0].get('precip') if forecast_data[0] else None,
            "today_pressure": lambda: forecast_data[0].get('pressure') if forecast_data[0] else None,
            "today_vis": lambda: forecast_data[0].get('vis') if forecast_data[0] else None,
            "today_cloud": lambda: forecast_data[0].get('cloud') if forecast_data[0] else None,
            "today_uv": lambda: f"{forecast_data[0].get('uvIndex', '未知')}级" if forecast_data[0] else "未知",
            
            # 未来天气
            "tomorrow_weather": lambda: self._format_future_weather(forecast_data[1]),
            "day3_weather": lambda: self._format_future_weather(forecast_data[2]),
        }
        
        formatter = value_mapping.get(sensor_key)
        if formatter:
            try:
                return formatter()
            except Exception:
                return self._get_sensor_default(sensor_key)
        
        return self._get_sensor_default(sensor_key)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
    
        try:
            data_content = data.get("data", {})
            city_info = data_content.get("city_info", {})
            daily_forecast = data_content.get("daily_forecast", [])
            api_source = data_content.get("api_source", {})
            
            # 基础属性
            attributes.update({
                "数据来源": api_source.get("city_api", "未知"),
                "天气数据来源": api_source.get("weather_api", "未知"),
                "JWT状态": data_content.get("jwt_status", "未知"),
                "更新时间": data_content.get("update_time", "未知")
            })
    
            # 城市名称传感器属性
            if sensor_key == "city_name":
                attributes.update({
                    "城市ID": city_info.get("id", "未知"),
                    "国家": city_info.get("country", "未知"),
                    "省份": city_info.get("adm1", "未知"),
                    "地区": city_info.get("adm2", "未知"),
                    "城市经度": city_info.get("lon", "未知"),
                    "城市纬度": city_info.get("lat", "未知"),
                    "时区": city_info.get("tz", "未知"),
                })
            
            # 天气传感器属性
            day_mapping = {
                "today_weather": 0,
                "tomorrow_weather": 1, 
                "day3_weather": 2
            }
            
            if sensor_key in day_mapping:
                day_data = self._get_day_forecast(daily_forecast, day_mapping[sensor_key])
                if day_data:
                    attributes.update({
                        "日出": day_data.get('sunrise', '未知'),
                        "日落": day_data.get('sunset', '未知'),
                        "月相": day_data.get('moonPhase', '未知'),
                        "白天天气": day_data.get('textDay', '未知'),
                        "夜间天气": day_data.get('textNight', '未知'),
                        "最低温度": day_data.get('tempMin', '未知'),
                        "最高温度": day_data.get('tempMax', '未知'),
                        "湿度": day_data.get('humidity', '未知'),
                        "紫外线指数": day_data.get('uvIndex', '未知'),
                    })
                    
                    # 为今天天气传感器添加详情属性
                    if sensor_key == "today_weather":
                        attributes["详情"] = self._format_today_detail(day_data)
            
            return attributes
    
        except Exception:
            return attributes
    
    def _format_today_detail(self, today_data: Dict[str, Any]) -> str:
        """格式化今日详情信息"""
        if not today_data:
            return "暂无数据"
        
        # 温度信息
        temp_str = self._format_temperature(today_data.get('tempMin'), today_data.get('tempMax'))
        
        # 湿度信息
        humidity = today_data.get('humidity', '未知')
        humidity_str = f"{humidity}%" if humidity != '未知' else "未知"
        
        # 风力信息
        wind_text = self._format_wind_text(
            today_data.get('windDirDay', ''), 
            today_data.get('windScaleDay', ''),
            today_data.get('windDirNight', ''),
            today_data.get('windScaleNight', '')
        )
        
        # 温馨提醒
        reminders = []
        
        # 检查白天天气是否含雨
        day_weather = today_data.get('textDay', '').lower()
        if any(rain_word in day_weather for rain_word in ['雨', '雪', '雷', 'storm', 'rain', 'snow', 'thunder']):
            reminders.append("出门带好雨具")
        
        # 检查紫外线等级
        uv_index = today_data.get('uvIndex')
        if uv_index and isinstance(uv_index, (int, str)):
            try:
                uv_value = int(uv_index)
                if uv_value >= 6:
                    reminders.append("紫外线较强，注意防晒")
                elif uv_value >= 3:
                    reminders.append("紫外线中等，适当防护")
            except (ValueError, TypeError):
                pass
        
        # 构建详情字符串
        detail_parts = [
            f"温度{temp_str}",
            f"湿度{humidity_str}", 
            f"风力{wind_text}"
        ]
        
        # 如果有特殊提醒，添加"温馨提醒："前缀
        if reminders:
            reminder_text = "；".join(reminders)
            detail_parts.append(f"温馨提醒：{reminder_text}")
        else:
            # 如果没有特殊提醒，直接显示祝福语，不加"温馨提醒"前缀
            detail_parts.append("天气适宜，祝您有美好的一天")
        
        return "，".join(detail_parts)

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        # 数值型传感器返回None，文本型传感器返回字符串
        numeric_sensors = [
            "today_humidity", "today_precip", "today_pressure", 
            "today_vis", "today_cloud" 
        ]
        
        if sensor_key in numeric_sensors:
            return None  # 数值型传感器返回None，HA会显示为"未知"
        
        # 文本型传感器返回加载提示
        text_defaults = {
            "city_name": "加载中...",
            "today_weather": "加载中...",
            "today_temp": "加载中...",  
            "today_wind": "加载中...", 
            "today_uv": "加载中...",
            "tomorrow_weather": "加载中...",
            "day3_weather": "加载中..."
        }
        return text_defaults.get(sensor_key, "加载中...")

    def _create_error_response(self, error_msg: str, error_type: str = "error") -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "data": None,
            "status": error_type,
            "error": error_msg,
            "update_time": datetime.now().isoformat()
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        required_fields = ["private_key", "project_id", "key_id"]
        for field in required_fields:
            if not config.get(field):
                raise ValueError(f"必须提供{field}")
        
        private_key = config.get("private_key", "").strip()
        if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
            raise ValueError("私钥格式不正确，必须是PEM格式")