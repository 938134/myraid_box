from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json
import aiohttp
import time
import jwt
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class WeatherService(BaseService):
    """使用官方JWT认证的每日天气服务（EdDSA算法）"""

    DEFAULT_API_URL = "https://APIHOST"
    DEFAULT_UPDATE_INTERVAL = 30
    
    # 常量定义
    WEATHER_API_PATHS = {
        "city_lookup": "/geo/v2/city/lookup",
        "weather_3d": "/v7/weather/3d"
    }
    
    # 传感器配置模板
    SENSOR_CONFIGS = [
        # 城市信息
        ("city_name", "城市", "mdi:city"),
        # 今日天气
        ("today_weather", "今天", "mdi:weather-partly-cloudy"),
        ("today_temp", "温度", "mdi:thermometer"),
        ("today_humidity", "湿度", "mdi:water-percent", "%", "humidity"),
        ("today_wind", "风力", "mdi:weather-windy"),
        ("today_precip", "降水", "mdi:weather-rainy", "mm"),
        ("today_pressure", "气压", "mdi:gauge", "hPa"),
        ("today_vis", "能见度", "mdi:eye", "km"),
        ("today_cloud", "云量", "mdi:cloud", "%"),
        ("today_uv", "紫外线", "mdi:weather-sunny-alert"),
        # 未来天气
        ("tomorrow_weather", "明天", "mdi:weather-partly-cloudy"),
        ("day3_weather", "后天", "mdi:weather-cloudy"),
    ]
        
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
    def icon(self) -> str:
        return "mdi:weather-cloudy-clock"
        
    @property
    def config_help(self) -> str:
        return "🌤️ 天气服务配置说明：\n1. 注册和风天气开发者账号：https://dev.qweather.com/\n2. 创建项目获取项目ID、密钥ID和EdDSA私钥\n3. 城市名称支持中文、拼音或LocationID"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔", "type": "int", "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "location": {
                "name": "城市名称", "type": "str", "default": "beij",
                "description": "城市名称或拼音（如：beij, shanghai）"
            },
            "api_host": {
                "name": "API主机", "type": "str", "default": "https://API HOST",
                "description": "天气API服务地址"
            },
            "private_key": {
                "name": "私钥", "type": "password", "default": "",
                "description": "EdDSA私钥（PEM格式）"
            },
            "project_id": {
                "name": "项目ID", "type": "str", "default": "PROJECT_ID",
                "description": "项目标识符"
            },
            "key_id": {
                "name": "密钥ID", "type": "str", "default": "KEY_ID",
                "description": "密钥标识符"
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """每日天气服务的传感器配置"""
        return [self._create_sensor_config(*config) for config in self.SENSOR_CONFIGS]

    def _generate_jwt_token(self, params: Dict[str, Any]) -> str:
        """生成JWT令牌"""
        private_key = params.get("private_key", "").strip()
        project_id = params.get("project_id", "YOUR_PROJECT_ID")
        key_id = params.get("key_id", "YOUR_KEY_ID")
        
        if not private_key:
            raise ValueError("私钥不能为空")
        
        payload = {
            'iat': int(time.time()) - 30,
            'exp': int(time.time()) + 900,
            'sub': project_id
        }
        
        return jwt.encode(payload, private_key, algorithm='EdDSA', headers={'kid': key_id})

    def _build_headers(self, jwt_token: str = "") -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"
        return headers

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数 - 支持JWT认证"""
        api_host = params.get("api_host", self.default_api_url).rstrip('/')
        url = f"{api_host}{self.WEATHER_API_PATHS['city_lookup']}"
        request_params = {"location": params.get("location", "beij")}
        
        try:
            jwt_token = self._generate_jwt_token(params)
            return url, request_params, self._build_headers(jwt_token)
        except Exception as e:
            _LOGGER.error("[每日天气] 构建请求失败: %s", str(e), exc_info=True)
            return url, request_params, self._build_headers()

    def _parse_api_response(self, response_data: Any) -> Dict[str, Any]:
        """解析API响应数据"""
        # 提取实际API响应
        if isinstance(response_data, dict) and "data" in response_data:
            api_response = response_data["data"]
            update_time = response_data.get("update_time", datetime.now().isoformat())
            status = response_data.get("status", "success")
        else:
            api_response = response_data
            update_time = datetime.now().isoformat()
            status = "success"

        if status != "success":
            return {"status": "error", "error": "API请求失败", "update_time": update_time}

        # 处理字符串响应
        if isinstance(api_response, str):
            try:
                api_response = json.loads(api_response)
            except json.JSONDecodeError as e:
                return {"status": "error", "error": f"JSON解析失败: {e}", "update_time": update_time}

        # 检查API返回码
        code = api_response.get("code")
        if code != "200":
            error_msg = api_response.get("message", "未知错误")
            error_type = "auth_error" if any(word in error_msg.lower() for word in ["auth", "token"]) else "error"
            return {"status": error_type, "error": f"{'认证' if error_type == 'auth_error' else 'API'}失败: {error_msg}", "update_time": update_time}

        return {
            "status": "success",
            "data": {
                "city_info": (api_response.get("location", []) or [{}])[0],
                "api_source": api_response.get("refer", {}).get("sources", ["未知"])[0],
                "jwt_status": "有效"
            },
            "update_time": update_time
        }

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析城市查询响应数据"""
        try:
            return self._parse_api_response(response_data)
        except Exception as e:
            _LOGGER.error("[每日天气] 解析响应数据时发生异常: %s", str(e), exc_info=True)
            return {"status": "error", "error": f"解析错误: {str(e)}", "update_time": datetime.now().isoformat()}

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以支持JWT认证"""
        await self._ensure_session()
        try:
            url, request_params, headers = self.build_request(params)
            
            if not headers.get("Authorization"):
                return self._create_error_response("JWT令牌生成失败", "auth_error")
            
            async with self._session.get(url, params=request_params, headers=headers) as resp:
                if resp.status == 401:
                    return self._create_error_response("认证失败: 无效的JWT令牌", "auth_error")
                
                resp.raise_for_status()
                data = await resp.json() if "application/json" in resp.headers.get("Content-Type", "").lower() else await resp.text()
                
                # 如果城市查询成功，继续获取天气数据
                if isinstance(data, dict) and data.get("code") == "200":
                    weather_data = await self._fetch_weather_data(params, data)
                    return self._create_success_response(weather_data)
                else:
                    return self._create_success_response(data, resp.status == 200, None if resp.status == 200 else f"HTTP {resp.status}")
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("[每日天气] 网络请求失败: %s", str(e), exc_info=True)
            return self._create_error_response(f"网络错误: {str(e)}")
        except Exception as e:
            _LOGGER.error("[每日天气] 请求失败: %s", str(e), exc_info=True)
            return self._create_error_response(str(e))

    def _create_success_response(self, data: Any, success: bool = True, error: Optional[str] = None) -> Dict[str, Any]:
        """创建成功响应"""
        return {
            "data": data,
            "status": "success" if success else "error",
            "error": error,
            "update_time": datetime.now().isoformat()
        }

    def _create_error_response(self, error_msg: str, error_type: str = "error") -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "data": None,
            "status": error_type,
            "error": error_msg,
            "update_time": datetime.now().isoformat()
        }

    async def _fetch_weather_data(self, params: Dict[str, Any], city_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据"""
        try:
            city_info = ((city_data.get("location", []) or [{}])[0])
            city_id = city_info.get("id")
            
            if not city_id:
                return self._create_weather_response(city_info, city_data.get("refer", {}), "城市ID无效")

            # 生成新的JWT令牌
            jwt_token = self._generate_jwt_token(params)
            api_host = params.get("api_host", self.default_api_url).rstrip('/')
            weather_url = f"{api_host}{self.WEATHER_API_PATHS['weather_3d']}"
            
            async with self._session.get(
                weather_url, 
                params={"location": city_id}, 
                headers=self._build_headers(jwt_token)
            ) as resp:
                if resp.status == 401:
                    return self._create_weather_response(city_info, city_data.get("refer", {}), "天气API认证失败", weather_api="认证失败")
                
                resp.raise_for_status()
                weather_response = await resp.json()
                
                if weather_response.get("code") != "200":
                    return self._create_weather_response(
                        city_info, city_data.get("refer", {}), "天气数据获取失败",
                        weather_api=f"错误: {weather_response.get('message')}"
                    )
                
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
            _LOGGER.error("[每日天气] 获取天气数据失败: %s", str(e), exc_info=True)
            city_info = ((city_data.get("location", []) or [{}])[0])
            return self._create_weather_response(
                city_info, city_data.get("refer", {}), "天气数据获取失败",
                weather_api=f"获取失败: {str(e)}"
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

    def _get_day_forecast(self, daily_forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天预报数据"""
        try:
            if not daily_forecast or not isinstance(daily_forecast, list):
                return None
            return daily_forecast[index] if index < len(daily_forecast) else None
        except (IndexError, TypeError, AttributeError) as e:
            _LOGGER.error("[每日天气] 获取第 %s 天预报数据失败: %s", index, str(e), exc_info=True)
            return None

    def _format_temperature(self, temp_min: Any, temp_max: Any) -> str:
        """格式化温度显示：最低温度~最高温度°C"""
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
                
        except Exception as e:
            _LOGGER.error("[每日天气] 温度格式化错误: %s", str(e), exc_info=True)
            return "未知"

    def _format_weather_text(self, weather_day: str, weather_night: str) -> str:
        """格式化天气文本：只在白天夜间不同时分别显示"""
        if not weather_day or not weather_night:
            return weather_day or weather_night or "未知"
        
        # 如果白天和夜间天气相同，直接返回
        if weather_day == weather_night:
            return weather_day
        
        # 白天夜间天气不同，分别显示
        return f"白天{weather_day}，夜间{weather_night}"

    def _format_wind_text(self, wind_dir_day: str, wind_scale_day: str, wind_dir_night: str, wind_scale_night: str) -> str:
        """格式化风力文本：只在白天夜间不同时分别显示"""
        # 添加风力单位
        day_wind = f"{wind_dir_day}{wind_scale_day}级" if wind_dir_day and wind_scale_day else ""
        night_wind = f"{wind_dir_night}{wind_scale_night}级" if wind_dir_night and wind_scale_night else ""
        
        if not day_wind and not night_wind:
            return "未知"
        if not day_wind:
            return night_wind
        if not night_wind:
            return day_wind
        
        # 如果白天和夜间风力相同，直接返回
        if day_wind == night_wind:
            return day_wind
        
        # 白天夜间风力不同，分别显示
        return f"白天{day_wind}，夜间{night_wind}"

    def _format_future_weather(self, weather_data: Optional[Dict]) -> str:
        """格式化未来天气信息（明天/后天）"""
        if not weather_data:
            return "暂无数据"
        
        weather_text = self._format_weather_text(
            weather_data.get('textDay', ''), 
            weather_data.get('textNight', '')
        )
        temp_str = self._format_temperature(weather_data.get('tempMin'), weather_data.get('tempMax'))
        humidity = weather_data.get('humidity', '未知')
        
        return f"{weather_text}，{temp_str}，湿度{humidity}%"

    def _generate_forecast_advice(self, today_data: Optional[Dict]) -> str:
        """生成天气预报和建议"""
        if not today_data:
            return "暂无数据"
        
        try:
            # 格式化天气和风力
            weather_text = self._format_weather_text(
                today_data.get('textDay', ''), 
                today_data.get('textNight', '')
            )
            wind_text = self._format_wind_text(
                today_data.get('windDirDay', ''), 
                today_data.get('windScaleDay', ''),
                today_data.get('windDirNight', ''),
                today_data.get('windScaleNight', '')
            )
            
            temp_str = self._format_temperature(today_data.get('tempMin'), today_data.get('tempMax'))
            humidity = today_data.get('humidity', '未知')
            
            # 构建基础预报
            forecast = f"{weather_text}，{temp_str}，湿度{humidity}%，{wind_text}"
            
            # 生成提醒建议
            reminders = self._generate_weather_reminders(today_data)
            if reminders:
                forecast += f"温馨提醒：{'；'.join(reminders)}"
            
            return forecast
            
        except Exception as e:
            _LOGGER.error("[每日天气] 生成预报建议失败: %s", str(e), exc_info=True)
            return "预报生成失败"

    def _generate_weather_reminders(self, weather_data: Dict) -> List[str]:
        """生成天气提醒"""
        reminders = []
        
        # 检查降水
        precip_day = weather_data.get('precip', '0.0')
        try:
            precip_value = float(precip_day) if precip_day else 0.0
            if precip_value > 0:
                reminders.append("出门带好雨具")
        except (ValueError, TypeError):
            pass
        
        # 检查紫外线
        uv_index = weather_data.get('uvIndex', '')
        try:
            uv_value = int(uv_index) if uv_index and uv_index.isdigit() else 0
            if uv_value >= 6:
                reminders.append("紫外线强烈，出门做好防晒")
            elif uv_value >= 3:
                reminders.append("紫外线中等，建议做好防晒")
        except (ValueError, TypeError):
            pass
        
        # 检查能见度
        visibility = weather_data.get('vis', '')
        try:
            vis_value = int(visibility) if visibility and visibility.isdigit() else 0
            if vis_value > 0:
                if vis_value < 1:
                    reminders.append("能见度很低，注意交通安全")
                elif vis_value < 3:
                    reminders.append("能见度较低，小心驾驶")
                elif vis_value < 5:
                    reminders.append("能见度一般，出行注意安全")
        except (ValueError, TypeError):
            pass
        
        return reminders

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据不同传感器key返回对应值"""
        if not data:
            return self._get_default_value(sensor_key, "数据加载中")
            
        if data.get("status") != "success":
            status = data.get("status")
            default_value = "认证失败" if status == "auth_error" else self._get_default_value(sensor_key, "数据加载中")
            return default_value
            
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
            "city_id": lambda: city_info.get("id", "未知"),
            
            # 今日天气
            "today_weather": lambda: self._format_weather_text(
                forecast_data[0].get('textDay', ''), 
                forecast_data[0].get('textNight', '')
            ) if forecast_data[0] else "暂无数据",
            "today_temp": lambda: self._format_temperature(forecast_data[0].get('tempMin'), forecast_data[0].get('tempMax')) if forecast_data[0] else "未知",
            "today_humidity": lambda: self._safe_int(forecast_data[0], 'humidity'),
            "today_wind": lambda: self._format_wind_text(
                forecast_data[0].get('windDirDay', ''), 
                forecast_data[0].get('windScaleDay', ''),
                forecast_data[0].get('windDirNight', ''),
                forecast_data[0].get('windScaleNight', '')
            ) if forecast_data[0] else "未知",
            "today_precip": lambda: f"{forecast_data[0].get('precip', '0.0')}" if forecast_data[0] else "未知",
            "today_pressure": lambda: self._safe_int(forecast_data[0], 'pressure'),
            "today_vis": lambda: self._safe_int(forecast_data[0], 'vis'),
            "today_cloud": lambda: self._safe_int(forecast_data[0], 'cloud'),
            "today_uv": lambda: f"{forecast_data[0].get('uvIndex', '未知')}级" if forecast_data[0] else "未知",
            
            # 未来天气
            "tomorrow_weather": lambda: self._format_future_weather(forecast_data[1]),
            "day3_weather": lambda: self._format_future_weather(forecast_data[2]),
        }
        
        formatter = value_mapping.get(sensor_key, lambda: "未知传感器")
        try:
            return formatter()
        except Exception as e:
            _LOGGER.error("[每日天气] 格式化传感器 %s 失败: %s", sensor_key, str(e), exc_info=True)
            return "未知"

    def _get_default_value(self, sensor_key: str, default: str) -> Any:
        """获取传感器默认值"""
        numeric_sensors = ["today_humidity", "today_pressure", "today_vis", "today_cloud"]
        return None if sensor_key in numeric_sensors else default

    def _safe_int(self, data: Optional[Dict], key: str) -> Optional[int]:
        """安全获取整数值"""
        return int(data[key]) if data and data.get(key) else None

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data or data.get("status") != "success":
            return {}
    
        try:
            data_content = data.get("data", {})
            city_info = data_content.get("city_info", {})
            daily_forecast = data_content.get("daily_forecast", [])
            api_source = data_content.get("api_source", {})
            
            # 基础属性
            attributes = {
                "数据来源": api_source.get("city_api", "未知"),
                "天气数据来源": api_source.get("weather_api", "未知"),
                "JWT状态": data_content.get("jwt_status", "未知"),
                "更新时间": data_content.get("update_time", "未知")
            }
    
            # 城市名称传感器属性
            if sensor_key == "city_name":
                attributes.update(self._get_city_attributes(city_info))
            
            # 天气传感器属性
            day_mapping = {
                "today_weather": 0,
                "tomorrow_weather": 1, 
                "day3_weather": 2
            }
            
            if sensor_key in day_mapping:
                day_data = self._get_day_forecast(daily_forecast, day_mapping[sensor_key])
                if day_data:
                    attributes.update(self._get_weather_attributes(day_data, sensor_key))
            
            return attributes
    
        except Exception as e:
            _LOGGER.error("[每日天气] 获取传感器属性失败: %s", str(e), exc_info=True)
            return {}

    def _get_city_attributes(self, city_info: Dict) -> Dict[str, Any]:
        """获取城市相关属性"""
        return {
            "城市ID": city_info.get("id", "未知"),
            "国家": city_info.get("country", "未知"),
            "省份": city_info.get("adm1", "未知"),
            "地区": city_info.get("adm2", "未知"),
            "城市经度": city_info.get("lon", "未知"),
            "城市纬度": city_info.get("lat", "未知"),
            "时区": city_info.get("tz", "未知"),
            "城市等级": city_info.get("rank", "未知")
        }

    def _get_weather_attributes(self, weather_data: Dict, sensor_key: str) -> Dict[str, Any]:
        """获取天气相关属性"""
        attributes = {
            "日出": weather_data.get('sunrise', '未知'),
            "日落": weather_data.get('sunset', '未知'),
            "月相": weather_data.get('moonPhase', '未知'),
            "月出": weather_data.get('moonrise', '未知'),
            "月落": weather_data.get('moonset', '未知'),
        }
        
        # 今日天气添加预报属性
        if sensor_key == "today_weather":
            attributes["预报"] = self._generate_forecast_advice(weather_data)
        else:
            # 未来天气添加详细属性
            attributes.update({
                "湿度": f"{weather_data.get('humidity', '未知')}%",
                "降水量": f"{weather_data.get('precip', '0.0')}",
                "气压": f"{weather_data.get('pressure', '未知')}hPa",
                "能见度": f"{weather_data.get('vis', '未知')}km", 
                "云量": f"{weather_data.get('cloud', '未知')}%",
                "紫外线": f"{weather_data.get('uvIndex', '未知')}级",
            })
        
        return attributes

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