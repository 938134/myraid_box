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
        """返回天气服务的配置说明"""
        return (
            "🌤️ 天气服务配置说明：\n"
            "1. 注册和风天气开发者账号：https://dev.qweather.com/\n"
            "2. 创建项目获取项目ID、密钥ID和EdDSA私钥\n"
            "3. 城市名称支持中文、拼音或LocationID"
        )

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
                "default": "https://API HOST",
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
        """每日天气服务的传感器配置"""
        configs = [
            # 城市信息 - 主传感器
            self._create_sensor_config("city_name", "城市", "mdi:city"),
            
            # 今日天气详细信息 - 主传感器
            self._create_sensor_config("today_weather", "今天", "mdi:weather-partly-cloudy"),
            self._create_sensor_config("today_temp", "温度", "mdi:thermometer"),
            self._create_sensor_config("today_humidity", "湿度", "mdi:water-percent", "%", "humidity"),
            self._create_sensor_config("today_wind", "风力", "mdi:weather-windy"),
            self._create_sensor_config("today_precip", "降水", "mdi:weather-rainy", "mm"),
            self._create_sensor_config("today_pressure", "气压", "mdi:gauge", "hPa"),
            self._create_sensor_config("today_vis", "能见度", "mdi:eye", "km"),
            self._create_sensor_config("today_cloud", "云量", "mdi:cloud", "%"),
            self._create_sensor_config("today_uv", "紫外线", "mdi:weather-sunny-alert"),
            
            # 明日天气信息 - 主传感器
            self._create_sensor_config("tomorrow_weather", "明天", "mdi:weather-partly-cloudy"),
            
            # 后天天气信息 - 主传感器
            self._create_sensor_config("day3_weather", "后天", "mdi:weather-cloudy"),
        ]
        return configs

    def _generate_jwt_token(self, params: Dict[str, Any]) -> str:
        """生成JWT令牌"""
        try:
            private_key = params.get("private_key", "").strip()
            project_id = params.get("project_id", "YOUR_PROJECT_ID")
            key_id = params.get("key_id", "YOUR_KEY_ID")
            
            if not private_key:
                raise ValueError("私钥不能为空")
            
            payload = {
                'iat': int(time.time()) - 30,  # 签发时间（提前30秒）
                'exp': int(time.time()) + 900,  # 过期时间（15分钟后）
                'sub': project_id
            }
            headers = {
                'kid': key_id
            }
            
            # 生成JWT令牌
            encoded_jwt = jwt.encode(
                payload, 
                private_key, 
                algorithm='EdDSA', 
                headers=headers
            )
            
            return encoded_jwt
            
        except Exception as e:
            _LOGGER.error("[每日天气] JWT令牌生成失败: %s", str(e), exc_info=True)
            raise

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数 - 支持JWT认证"""
        api_host = params.get("api_host", self.default_api_url).rstrip('/')
        location = params.get("location", "beij")
        
        # 构建城市查询URL
        url = f"{api_host}/geo/v2/city/lookup"
        request_params = {
            "location": location
        }
        
        try:
            # 生成JWT令牌
            jwt_token = self._generate_jwt_token(params)
            
            # 构建JWT认证头
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}"
            }
            
            return url, request_params, headers
            
        except Exception as e:
            _LOGGER.error("[每日天气] 构建请求失败: %s", str(e), exc_info=True)
            # 返回一个会失败的请求，让错误处理机制接管
            headers = {
                "Accept": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}"
            }
            return url, request_params, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析城市查询响应数据"""
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

            # 检查API返回码
            code = api_response.get("code")
            
            if code != "200":
                error_msg = api_response.get("message", "未知错误")
                # 检查是否是认证错误
                if "auth" in error_msg.lower() or "token" in error_msg.lower():
                    return {
                        "status": "auth_error",
                        "error": f"认证失败: {error_msg}",
                        "update_time": update_time
                    }
                return {
                    "status": "error",
                    "error": f"API错误: {error_msg}",
                    "update_time": update_time
                }

            # 获取城市数据
            location_data = api_response.get("location", [])
            
            if not location_data:
                return {
                    "status": "error",
                    "error": "未找到城市数据",
                    "update_time": update_time
                }

            # 提取第一个匹配的城市信息
            city_info = location_data[0] if location_data else {}
            
            # 返回标准化数据
            result = {
                "status": "success",
                "data": {
                    "city_info": city_info,
                    "api_source": api_response.get("refer", {}).get("sources", ["未知"])[0],
                    "jwt_status": "有效"
                },
                "update_time": update_time
            }
            return result

        except Exception as e:
            _LOGGER.error("[每日天气] 解析响应数据时发生异常: %s", str(e), exc_info=True)
            return {
                "status": "error",
                "error": f"解析错误: {str(e)}",
                "update_time": datetime.now().isoformat()
            }

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以支持JWT认证"""
        await self._ensure_session()
        try:
            url, request_params, headers = self.build_request(params)
            
            # 检查是否生成了认证头
            if not headers.get("Authorization"):
                return {
                    "data": None,
                    "status": "auth_error",
                    "error": "JWT令牌生成失败",
                    "update_time": datetime.now().isoformat()
                }
            
            async with self._session.get(url, params=request_params, headers=headers) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                
                if resp.status == 401:
                    return {
                        "data": None,
                        "status": "auth_error",
                        "error": "认证失败: 无效的JWT令牌",
                        "update_time": datetime.now().isoformat()
                    }
                
                resp.raise_for_status()
                
                if "application/json" in content_type:
                    data = await resp.json()
                else:
                    data = await resp.text()
                
                # 如果城市查询成功，继续获取天气数据
                if isinstance(data, dict) and data.get("code") == "200":
                    weather_data = await self._fetch_weather_data(params, data)
                    result = {
                        "data": weather_data,
                        "status": "success",
                        "error": None,
                        "update_time": datetime.now().isoformat()
                    }
                    return result
                else:
                    result = {
                        "data": data,
                        "status": "success" if resp.status == 200 else "error",
                        "error": None if resp.status == 200 else f"HTTP {resp.status}",
                        "update_time": datetime.now().isoformat()
                    }
                    return result
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("[每日天气] 网络请求失败: %s", str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": f"网络错误: {str(e)}",
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            _LOGGER.error("[每日天气] 请求失败: %s", str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": str(e),
                "update_time": datetime.now().isoformat()
            }

    async def _fetch_weather_data(self, params: Dict[str, Any], city_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据 - 使用正确的API路径"""
        try:
            location_data = city_data.get("location", [])
            
            if not location_data:
                return {
                    "city_info": {},
                    "weather_info": {},
                    "api_source": {},
                    "jwt_status": "城市数据无效"
                }
                
            city_info = location_data[0]
            city_id = city_info.get("id")
            
            if not city_id:
                return {
                    "city_info": city_info,
                    "weather_info": {},
                    "api_source": city_data.get("refer", {}),
                    "jwt_status": "城市ID无效"
                }
            
            # 生成新的JWT令牌（避免过期）
            jwt_token = self._generate_jwt_token(params)
            
            # 构建天气查询URL - 使用正确的API路径
            api_host = params.get("api_host", self.default_api_url).rstrip('/')
            
            # 使用 /v7/weather/3d 接口获取3天天气预报
            weather_url = f"{api_host}/v7/weather/3d"
            weather_params = {
                "location": city_id
            }
            
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json"
            }
            
            async with self._session.get(weather_url, params=weather_params, headers=headers) as resp:
                if resp.status == 401:
                    return {
                        "city_info": city_info,
                        "weather_info": {},
                        "api_source": {
                            "city_api": city_data.get("refer", {}).get("sources", ["未知"])[0],
                            "weather_api": "认证失败"
                        },
                        "jwt_status": "天气API认证失败"
                    }
                
                resp.raise_for_status()
                weather_response = await resp.json()
                
                # 检查天气API返回码
                if weather_response.get("code") != "200":
                    return {
                        "city_info": city_info,
                        "weather_info": {},
                        "api_source": {
                            "city_api": city_data.get("refer", {}).get("sources", ["未知"])[0],
                            "weather_api": f"错误: {weather_response.get('message')}"
                        },
                        "jwt_status": "天气数据获取失败"
                    }
                
                # 合并城市信息和天气信息
                merged_data = {
                    "city_info": city_info,
                    "weather_data": weather_response,  # 保存完整的天气响应
                    "daily_forecast": weather_response.get("daily", []),
                    "api_source": {
                        "city_api": city_data.get("refer", {}).get("sources", ["未知"])[0],
                        "weather_api": weather_response.get("refer", {}).get("sources", ["未知"])[0]
                    },
                    "update_time": weather_response.get("updateTime", "未知"),
                    "jwt_status": "有效"
                }
                
                return merged_data
                
        except Exception as e:
            _LOGGER.error("[每日天气] 获取天气数据失败: %s", str(e), exc_info=True)
            # 返回城市数据，即使天气数据获取失败
            location_data = city_data.get("location", [])
            return {
                "city_info": location_data[0] if location_data else {},
                "weather_info": {},
                "api_source": {
                    "city_api": city_data.get("refer", {}).get("sources", ["未知"])[0],
                    "weather_api": f"获取失败: {str(e)}"
                },
                "jwt_status": "天气数据获取失败"
            }

    def _get_day_forecast(self, daily_forecast: List[Dict], index: int) -> Optional[Dict]:
        """安全获取某天预报数据"""
        try:
            if not daily_forecast or not isinstance(daily_forecast, list):
                _LOGGER.debug("[每日天气] 每日预报数据无效: %s", daily_forecast)
                return None
            result = daily_forecast[index] if index < len(daily_forecast) else None
            _LOGGER.debug("[每日天气] 获取第 %s 天预报数据: %s", index, bool(result))
            return result
        except (IndexError, TypeError, AttributeError) as e:
            _LOGGER.error("[每日天气] 获取第 %s 天预报数据失败: %s", index, str(e), exc_info=True)
            return None

    def _format_temperature(self, temp_min: Any, temp_max: Any) -> str:
        """格式化温度显示：最低温度~最高温度°C"""
        try:
            # 调试日志
            _LOGGER.debug("[每日天气] 温度格式化输入 - temp_min: %s (%s), temp_max: %s (%s)", 
                         temp_min, type(temp_min), temp_max, type(temp_max))
            
            # 处理None值
            if temp_min is None and temp_max is None:
                return "未知"
            
            # 转换为字符串并清理
            min_temp = str(temp_min).strip() if temp_min is not None else ""
            max_temp = str(temp_max).strip() if temp_max is not None else ""
            
            # 调试处理后的值
            _LOGGER.debug("[每日天气] 处理后的温度 - min_temp: %s, max_temp: %s", min_temp, max_temp)
            
            # 检查空值或无效值
            if not min_temp and not max_temp:
                return "未知"
            
            # 如果只有一个温度值
            if not min_temp and max_temp:
                return f"{max_temp}°C"
            elif min_temp and not max_temp:
                return f"{min_temp}°C"
            
            # 两个温度值都存在
            if min_temp == max_temp:
                return f"{min_temp}°C"
            else:
                return f"{min_temp}~{max_temp}°C"
                
        except Exception as e:
            _LOGGER.error("[每日天气] 温度格式化错误: %s", str(e), exc_info=True)
            return "未知"

    def _format_wind(self, wind_dir_day: str, wind_scale_day: str, wind_dir_night: str, wind_scale_night: str) -> str:
        """格式化风力显示：白天风向风力，夜间风向风力"""
        try:
            day_wind = f"{wind_dir_day}{wind_scale_day}" if wind_dir_day and wind_scale_day else "未知"
            night_wind = f"{wind_dir_night}{wind_scale_night}" if wind_dir_night and wind_scale_night else "未知"
            return f"白天{day_wind}，夜间{night_wind}"
        except Exception as e:
            _LOGGER.error("[每日天气] 风力格式化错误: %s", str(e))
            return "未知"

    def _format_tomorrow_weather(self, tomorrow_data: Optional[Dict]) -> str:
        """格式化明天天气信息"""
        if not tomorrow_data:
            return "暂无数据"
        
        weather_day = tomorrow_data.get('textDay', '未知')
        weather_night = tomorrow_data.get('textNight', '未知')
        temp_str = self._format_temperature(tomorrow_data.get('tempMin'), tomorrow_data.get('tempMax'))
        humidity = tomorrow_data.get('humidity', '未知')
        
        return f"白天{weather_day}，夜间{weather_night}，{temp_str}，湿度{humidity}%"

    def _format_day3_weather(self, day3_data: Optional[Dict]) -> str:
        """格式化后天天气信息"""
        if not day3_data:
            return "暂无数据"
        
        weather_day = day3_data.get('textDay', '未知')
        weather_night = day3_data.get('textNight', '未知')
        temp_str = self._format_temperature(day3_data.get('tempMin'), day3_data.get('tempMax'))
        humidity = day3_data.get('humidity', '未知')
        
        return f"白天{weather_day}，夜间{weather_night}，{temp_str}，湿度{humidity}%"

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据不同传感器key返回对应值"""
        if not data:
            _LOGGER.debug("[每日天气] 传感器 %s: 无数据", sensor_key)
            return None if sensor_key in ["today_humidity", "today_pressure", "today_vis", "today_cloud"] else "数据加载中"
            
        if data.get("status") != "success":
            status = data.get("status")
            _LOGGER.debug("[每日天气] 传感器 %s: 状态错误 - %s", sensor_key, status)
            if status == "auth_error":
                return "认证失败"
            return None if sensor_key in ["today_humidity", "today_pressure", "today_vis", "today_cloud"] else "数据加载中"
            
        data_content = data.get("data", {})
        city_info = data_content.get("city_info", {})
        daily_forecast = data_content.get("daily_forecast", [])
        
        # 获取各天预报数据
        today_data = self._get_day_forecast(daily_forecast, 0)
        tomorrow_data = self._get_day_forecast(daily_forecast, 1)
        day3_data = self._get_day_forecast(daily_forecast, 2)
        
        # 调试温度数据
        if sensor_key == "today_temp":
            _LOGGER.debug("[每日天气] 今日温度数据: %s", today_data)
            if today_data:
                _LOGGER.debug("[每日天气] 温度字段 - tempMin: %s, tempMax: %s", 
                             today_data.get('tempMin'), today_data.get('tempMax'))
        
        value_mapping = {
            # 城市信息传感器
            "city_name": lambda: city_info.get("name", "未知"),
            "city_id": lambda: city_info.get("id", "未知"),
            
            # 今日天气详细信息
            "today_weather": lambda: f"白天{today_data.get('textDay', '未知')}，夜间{today_data.get('textNight', '未知')}" if today_data else "暂无数据",
            "today_temp": lambda: self._format_temperature(today_data.get('tempMin'), today_data.get('tempMax')) if today_data else "未知",
            "today_humidity": lambda: int(today_data.get('humidity')) if today_data and today_data.get('humidity') else None,
            "today_wind": lambda: self._format_wind(
                today_data.get('windDirDay', '未知'), 
                today_data.get('windScaleDay', '未知'),
                today_data.get('windDirNight', '未知'),
                today_data.get('windScaleNight', '未知')
            ) if today_data else "未知",
            "today_precip": lambda: f"{today_data.get('precip', '0.0')}" if today_data else "未知",
            "today_pressure": lambda: int(today_data.get('pressure')) if today_data and today_data.get('pressure') else None,
            "today_vis": lambda: int(today_data.get('vis')) if today_data and today_data.get('vis') else None,
            "today_cloud": lambda: int(today_data.get('cloud')) if today_data and today_data.get('cloud') else None,
            "today_uv": lambda: f"{today_data.get('uvIndex', '未知')}级" if today_data else "未知",
            
            # 明日天气信息（合并显示）
            "tomorrow_weather": lambda: self._format_tomorrow_weather(tomorrow_data),
            
            # 后天天气信息（合并显示）
            "day3_weather": lambda: self._format_day3_weather(day3_data),
        }
        
        formatter = value_mapping.get(sensor_key, lambda: "未知传感器")
        try:
            result = formatter()
            # 特别记录温度传感器的调试信息
            if sensor_key == "today_temp":
                _LOGGER.debug("[每日天气] 今日温度传感器最终结果: %s", result)
            return result
        except Exception as e:
            _LOGGER.error("[每日天气] 格式化传感器 %s 失败: %s", sensor_key, str(e), exc_info=True)
            return "未知"

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性 - 用于属性传感器数据源"""
        if not data or data.get("status") != "success":
            return {}
    
        try:
            data_content = data.get("data", {})
            city_info = data_content.get("city_info", {})
            daily_forecast = data_content.get("daily_forecast", [])
            api_source = data_content.get("api_source", {})
            jwt_status = data_content.get("jwt_status", "未知")
            update_time = data_content.get("update_time", "未知")
            
            attributes = {
                "数据来源": api_source.get("city_api", "未知"),
                "天气数据来源": api_source.get("weather_api", "未知"),
                "JWT状态": jwt_status,
                "更新时间": update_time
            }
    
            # 城市名称传感器的属性
            if sensor_key == "city_name":
                attributes.update({
                    "城市ID": city_info.get("id", "未知"),
                    "国家": city_info.get("country", "未知"),
                    "省份": city_info.get("adm1", "未知"),
                    "地区": city_info.get("adm2", "未知"),
                    "城市经度": city_info.get("lon", "未知"),
                    "城市纬度": city_info.get("lat", "未知"),
                    "时区": city_info.get("tz", "未知"),
                    "城市等级": city_info.get("rank", "未知")
                })
            
            # 今日天气传感器的属性
            today_data = self._get_day_forecast(daily_forecast, 0)
            if today_data and sensor_key == "today_weather":
                attributes.update({
                    "日出": today_data.get('sunrise', '未知'),
                    "日落": today_data.get('sunset', '未知'),
                    "月相": today_data.get('moonPhase', '未知'),
                    "月出": today_data.get('moonrise', '未知'),
                    "月落": today_data.get('moonset', '未知'),
                })
            
            # 明日天气传感器的属性
            tomorrow_data = self._get_day_forecast(daily_forecast, 1)
            if tomorrow_data and sensor_key == "tomorrow_weather":
                attributes.update({
                    "日出": tomorrow_data.get('sunrise', '未知'),
                    "日落": tomorrow_data.get('sunset', '未知'),
                    "月相": tomorrow_data.get('moonPhase', '未知'),
                    "月出": tomorrow_data.get('moonrise', '未知'),
                    "月落": tomorrow_data.get('moonset', '未知'),
                    "湿度": f"{tomorrow_data.get('humidity', '未知')}%",
                    "降水量": f"{tomorrow_data.get('precip', '0.0')}",
                    "气压": f"{tomorrow_data.get('pressure', '未知')}hPa",
                    "能见度": f"{tomorrow_data.get('vis', '未知')}km",
                    "云量": f"{tomorrow_data.get('cloud', '未知')}%",
                    "紫外线": f"{tomorrow_data.get('uvIndex', '未知')}级",
                })
            
            # 后天天气传感器的属性
            day3_data = self._get_day_forecast(daily_forecast, 2)
            if day3_data and sensor_key == "day3_weather":
                attributes.update({
                    "日出": day3_data.get('sunrise', '未知'),
                    "日落": day3_data.get('sunset', '未知'),
                    "月相": day3_data.get('moonPhase', '未知'),
                    "月出": day3_data.get('moonrise', '未知'),
                    "月落": day3_data.get('moonset', '未知'),
                    "湿度": f"{day3_data.get('humidity', '未知')}%",
                    "降水量": f"{day3_data.get('precip', '0.0')}",
                    "气压": f"{day3_data.get('pressure', '未知')}hPa",
                    "能见度": f"{day3_data.get('vis', '未知')}km",
                    "云量": f"{day3_data.get('cloud', '未知')}%",
                    "紫外线": f"{day3_data.get('uvIndex', '未知')}级",
                })
    
            return attributes
    
        except Exception as e:
            _LOGGER.error("[每日天气] 获取传感器属性失败: %s", str(e), exc_info=True)
            return {}

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        required_fields = ["private_key", "project_id", "key_id"]
        for field in required_fields:
            if not config.get(field):
                error_msg = f"必须提供{field}"
                raise ValueError(error_msg)
        
        # 验证私钥格式
        private_key = config.get("private_key", "").strip()
        if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
            raise ValueError("私钥格式不正确，必须是PEM格式")