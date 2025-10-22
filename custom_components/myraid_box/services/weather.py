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
    """使用官方JWT认证的天气服务（EdDSA算法）"""

    DEFAULT_API_URL = "https://your_api_host"
    DEFAULT_UPDATE_INTERVAL = 30
        
    @property
    def service_id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "天气服务"

    @property
    def description(self) -> str:
        return "使用官方JWT认证获取3天天气预报"

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
                "default": "https://your_api_host",
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
                "default": "YOUR_PROJECT_ID",
                "description": "项目标识符"
            },
            "key_id": {
                "name": "密钥ID",
                "type": "str",
                "default": "YOUR_KEY_ID",
                "description": "密钥标识符"
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """天气服务的传感器配置"""
        _LOGGER.error("[天气服务] 开始生成传感器配置")
        configs = [
            # 城市信息（简化版）
            self._create_sensor_config("city_name", "城市名称", "mdi:city", sort_order=1),
            self._create_sensor_config("city_id", "城市ID", "mdi:identifier", sort_order=2),
            
            # 今日天气信息
            self._create_sensor_config("today_weather", "今日天气", "mdi:weather-partly-cloudy", sort_order=3),
            self._create_sensor_config("today_temp", "今日温度", "mdi:thermometer", "°C", sort_order=4),
            self._create_sensor_config("today_humidity", "今日湿度", "mdi:water-percent", "%", "humidity", sort_order=5),
            self._create_sensor_config("today_wind", "今日风力", "mdi:weather-windy", sort_order=6),
            self._create_sensor_config("today_uv", "紫外线指数", "mdi:weather-sunny-alert", sort_order=7),
            self._create_sensor_config("today_precip", "降水量", "mdi:weather-rainy", "mm", sort_order=8),
            
            # 明日天气信息
            self._create_sensor_config("tomorrow_weather", "明日天气", "mdi:weather-partly-cloudy", sort_order=9),
            self._create_sensor_config("tomorrow_temp", "明日温度", "mdi:thermometer", "°C", sort_order=10),
            
            # 后天天气信息
            self._create_sensor_config("day3_weather", "后天天气", "mdi:weather-cloudy", sort_order=11),
            self._create_sensor_config("day3_temp", "后天温度", "mdi:thermometer", "°C", sort_order=12),
            
            # 状态信息
            self._create_sensor_config("update_time", "更新时间", "mdi:clock", sort_order=13),
            self._create_sensor_config("jwt_status", "认证状态", "mdi:security", sort_order=14)
        ]
        _LOGGER.error("[天气服务] 传感器配置生成完成，共 %d 个传感器", len(configs))
        return configs

    def _generate_jwt_token(self, params: Dict[str, Any]) -> str:
        """生成JWT令牌"""
        try:
            private_key = params.get("private_key", "").strip()
            project_id = params.get("project_id", "YOUR_PROJECT_ID")
            key_id = params.get("key_id", "YOUR_KEY_ID")
            
            _LOGGER.error("[天气服务] 开始生成JWT令牌")
            
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
            
            _LOGGER.error("[天气服务] JWT令牌生成成功")
            return encoded_jwt
            
        except Exception as e:
            _LOGGER.error("[天气服务] JWT令牌生成失败: %s", str(e), exc_info=True)
            raise

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数 - 支持JWT认证"""
        _LOGGER.error("[天气服务] 开始构建请求")
        api_host = params.get("api_host", self.default_api_url).rstrip('/')
        location = params.get("location", "beij")
        
        _LOGGER.error("[天气服务] API主机: %s, 城市: %s", api_host, location)
        
        # 构建城市查询URL
        url = f"{api_host}/geo/v2/city/lookup"
        request_params = {
            "location": location
        }
        
        _LOGGER.error("[天气服务] 请求URL: %s, 参数: %s", url, request_params)
        
        try:
            # 生成JWT令牌
            jwt_token = self._generate_jwt_token(params)
            
            # 构建JWT认证头
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}"
            }
            
            _LOGGER.error("[天气服务] 请求头构建成功")
            
            return url, request_params, headers
            
        except Exception as e:
            _LOGGER.error("[天气服务] 构建请求失败: %s", str(e), exc_info=True)
            # 返回一个会失败的请求，让错误处理机制接管
            headers = {
                "Accept": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}"
            }
            return url, request_params, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析城市查询响应数据"""
        _LOGGER.error("[天气服务] 开始解析响应数据")
        
        try:
            # 第一层：协调器包装的数据
            if isinstance(response_data, dict) and "data" in response_data:
                api_response = response_data["data"]
                update_time = response_data.get("update_time", datetime.now().isoformat())
                status = response_data.get("status", "success")
                _LOGGER.error("[天气服务] 协调器数据状态: %s", status)
            else:
                api_response = response_data
                update_time = datetime.now().isoformat()
                status = "success"
                _LOGGER.error("[天气服务] 直接API响应")

            if status != "success":
                _LOGGER.error("[天气服务] API请求失败状态: %s", status)
                return {
                    "status": "error",
                    "error": "API请求失败",
                    "update_time": update_time
                }

            # 如果api_response是字符串，尝试解析JSON
            if isinstance(api_response, str):
                _LOGGER.error("[天气服务] 响应为字符串，尝试解析JSON")
                try:
                    api_response = json.loads(api_response)
                    _LOGGER.error("[天气服务] JSON解析成功")
                except json.JSONDecodeError as e:
                    _LOGGER.error("[天气服务] JSON解析失败: %s", e)
                    return {
                        "status": "error", 
                        "error": f"JSON解析失败: {e}",
                        "update_time": update_time
                    }

            _LOGGER.error("[天气服务] API响应类型: %s", type(api_response))

            # 检查API返回码
            code = api_response.get("code")
            _LOGGER.error("[天气服务] API返回码: %s", code)
            
            if code != "200":
                error_msg = api_response.get("message", "未知错误")
                _LOGGER.error("[天气服务] API错误消息: %s", error_msg)
                # 检查是否是认证错误
                if "auth" in error_msg.lower() or "token" in error_msg.lower():
                    _LOGGER.error("[天气服务] 认证错误 detected")
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
            _LOGGER.error("[天气服务] 城市数据数量: %d", len(location_data))
            
            if not location_data:
                _LOGGER.error("[天气服务] 未找到城市数据")
                return {
                    "status": "error",
                    "error": "未找到城市数据",
                    "update_time": update_time
                }

            # 提取第一个匹配的城市信息
            city_info = location_data[0] if location_data else {}
            _LOGGER.error("[天气服务] 城市信息: %s", city_info)
            
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
            _LOGGER.error("[天气服务] 解析结果成功")
            return result

        except Exception as e:
            _LOGGER.error("[天气服务] 解析响应数据时发生异常: %s", str(e), exc_info=True)
            return {
                "status": "error",
                "error": f"解析错误: {str(e)}",
                "update_time": datetime.now().isoformat()
            }

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以支持JWT认证"""
        _LOGGER.error("[天气服务] 开始获取数据")
        await self._ensure_session()
        try:
            url, request_params, headers = self.build_request(params)
            
            _LOGGER.error("[天气服务] 最终请求参数 - URL: %s", url)
            
            # 检查是否生成了认证头
            if not headers.get("Authorization"):
                _LOGGER.error("[天气服务] 未生成认证头，返回认证错误")
                return {
                    "data": None,
                    "status": "auth_error",
                    "error": "JWT令牌生成失败",
                    "update_time": datetime.now().isoformat()
                }
            
            _LOGGER.error("[天气服务] 发送HTTP请求")
            async with self._session.get(url, params=request_params, headers=headers) as resp:
                _LOGGER.error("[天气服务] HTTP响应状态: %s", resp.status)
                
                content_type = resp.headers.get("Content-Type", "").lower()
                _LOGGER.error("[天气服务] 响应Content-Type: %s", content_type)
                
                if resp.status == 401:
                    _LOGGER.error("[天气服务] 认证失败 (401)")
                    return {
                        "data": None,
                        "status": "auth_error",
                        "error": "认证失败: 无效的JWT令牌",
                        "update_time": datetime.now().isoformat()
                    }
                
                resp.raise_for_status()
                _LOGGER.error("[天气服务] HTTP请求成功")
                
                if "application/json" in content_type:
                    data = await resp.json()
                    _LOGGER.error("[天气服务] 响应JSON数据获取成功")
                else:
                    data = await resp.text()
                    _LOGGER.error("[天气服务] 响应文本数据: %s", data)
                
                # 如果城市查询成功，继续获取天气数据
                if isinstance(data, dict) and data.get("code") == "200":
                    _LOGGER.error("[天气服务] 城市查询成功，开始获取天气数据")
                    weather_data = await self._fetch_weather_data(params, data)
                    result = {
                        "data": weather_data,
                        "status": "success",
                        "error": None,
                        "update_time": datetime.now().isoformat()
                    }
                    _LOGGER.error("[天气服务] 最终返回结果成功")
                    return result
                else:
                    _LOGGER.error("[天气服务] 城市查询未返回成功状态")
                    result = {
                        "data": data,
                        "status": "success" if resp.status == 200 else "error",
                        "error": None if resp.status == 200 else f"HTTP {resp.status}",
                        "update_time": datetime.now().isoformat()
                    }
                    _LOGGER.error("[天气服务] 返回结果: %s", result)
                    return result
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("[天气服务] 网络请求失败: %s", str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": f"网络错误: {str(e)}",
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            _LOGGER.error("[天气服务] 请求失败: %s", str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": str(e),
                "update_time": datetime.now().isoformat()
            }

    async def _fetch_weather_data(self, params: Dict[str, Any], city_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取天气数据 - 使用正确的API路径"""
        _LOGGER.error("[天气服务] 开始获取天气数据")
        try:
            location_data = city_data.get("location", [])
            _LOGGER.error("[天气服务] 城市数据中的位置数据: %s", location_data)
            
            if not location_data:
                _LOGGER.error("[天气服务] 城市数据为空")
                return {
                    "city_info": {},
                    "weather_info": {},
                    "api_source": {},
                    "jwt_status": "城市数据无效"
                }
                
            city_info = location_data[0]
            city_id = city_info.get("id")
            _LOGGER.error("[天气服务] 城市ID: %s", city_id)
            
            if not city_id:
                _LOGGER.error("[天气服务] 城市ID无效")
                return {
                    "city_info": city_info,
                    "weather_info": {},
                    "api_source": city_data.get("refer", {}),
                    "jwt_status": "城市ID无效"
                }
            
            # 生成新的JWT令牌（避免过期）
            jwt_token = self._generate_jwt_token(params)
            _LOGGER.error("[天气服务] 为天气API生成的新JWT令牌")
            
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
            
            _LOGGER.error("[天气服务] 天气API请求 - URL: %s, Params: %s", weather_url, weather_params)
            
            async with self._session.get(weather_url, params=weather_params, headers=headers) as resp:
                _LOGGER.error("[天气服务] 天气API响应状态: %s", resp.status)
                
                if resp.status == 401:
                    _LOGGER.error("[天气服务] 天气API认证失败")
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
                _LOGGER.error("[天气服务] 天气API响应数据获取成功")
                
                # 检查天气API返回码
                if weather_response.get("code") != "200":
                    _LOGGER.error("[天气服务] 天气API返回错误: %s", weather_response.get("message"))
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
                
                _LOGGER.error("[天气服务] 天气数据合并成功，预报天数: %d", len(merged_data["daily_forecast"]))
                return merged_data
                
        except Exception as e:
            _LOGGER.error("[天气服务] 获取天气数据失败: %s", str(e), exc_info=True)
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
            return daily_forecast[index] if index < len(daily_forecast) else None
        except (IndexError, TypeError):
            return None

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据不同传感器key返回对应值"""
        _LOGGER.error("[天气服务] 格式化传感器值 - 传感器: %s", sensor_key)
        
        if not data:
            _LOGGER.error("[天气服务] 数据为空")
            return None if "humidity" in sensor_key else "数据加载中"
            
        if data.get("status") != "success":
            status = data.get("status")
            _LOGGER.error("[天气服务] 数据状态异常: %s", status)
            if status == "auth_error":
                return "认证失败"
            return None if "humidity" in sensor_key else "数据加载中"
            
        data_content = data.get("data", {})
        city_info = data_content.get("city_info", {})
        daily_forecast = data_content.get("daily_forecast", [])
        jwt_status = data_content.get("jwt_status", "未知")
        update_time = data_content.get("update_time", "未知")
        
        _LOGGER.error("[天气服务] 数据内容 - 预报天数: %d", len(daily_forecast))
        
        # 获取各天预报数据
        today_data = self._get_day_forecast(daily_forecast, 0)
        tomorrow_data = self._get_day_forecast(daily_forecast, 1)
        day3_data = self._get_day_forecast(daily_forecast, 2)
        
        value_mapping = {
            # 城市信息传感器（简化版）
            "city_name": lambda: city_info.get("name", "未知"),
            "city_id": lambda: city_info.get("id", "未知"),
            
            # 今日天气信息
            "today_weather": lambda: f"{today_data.get('textDay', '未知')}转{today_data.get('textNight', '未知')}" if today_data else "暂无数据",
            "today_temp": lambda: f"{today_data.get('tempMin', 'N/A')}~{today_data.get('tempMax', 'N/A')}°C" if today_data else "未知",
            "today_humidity": lambda: int(today_data.get('humidity')) if today_data and today_data.get('humidity') else None,
            "today_wind": lambda: f"{today_data.get('windDirDay', '未知')}{today_data.get('windScaleDay', '未知')}级" if today_data else "未知",
            "today_uv": lambda: f"{today_data.get('uvIndex', '未知')}级" if today_data else "未知",
            "today_precip": lambda: f"{today_data.get('precip', '0.0')}mm" if today_data else "未知",
            
            # 明日天气信息
            "tomorrow_weather": lambda: f"{tomorrow_data.get('textDay', '未知')}转{tomorrow_data.get('textNight', '未知')}" if tomorrow_data else "暂无数据",
            "tomorrow_temp": lambda: f"{tomorrow_data.get('tempMin', 'N/A')}~{tomorrow_data.get('tempMax', 'N/A')}°C" if tomorrow_data else "未知",
            
            # 后天天气信息
            "day3_weather": lambda: f"{day3_data.get('textDay', '未知')}转{day3_data.get('textNight', '未知')}" if day3_data else "暂无数据",
            "day3_temp": lambda: f"{day3_data.get('tempMin', 'N/A')}~{day3_data.get('tempMax', 'N/A')}°C" if day3_data else "未知",
            
            # 状态信息
            "update_time": lambda: update_time,
            "jwt_status": lambda: jwt_status
        }
        
        formatter = value_mapping.get(sensor_key, lambda: "未知传感器")
        result = formatter()
        _LOGGER.error("[天气服务] 传感器 %s 格式化结果: %s", sensor_key, result)
        return result

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        _LOGGER.error("[天气服务] 获取传感器属性 - 传感器: %s", sensor_key)
        
        if not data or data.get("status") != "success":
            _LOGGER.error("[天气服务] 无法获取属性，数据状态异常")
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
                "JWT状态": jwt_status,
                "更新时间": update_time
            }
    
            # 为城市相关传感器添加详细属性
            if sensor_key in ["city_name", "city_id"]:
                attributes.update({
                    "国家": city_info.get("country", "未知"),
                    "省份": city_info.get("adm1", "未知"),
                    "地区": city_info.get("adm2", "未知"),
                    "城市经度": city_info.get("lon", "未知"),
                    "城市纬度": city_info.get("lat", "未知"),
                    "时区": city_info.get("tz", "未知"),
                    "城市等级": city_info.get("rank", "未知")
                })
            
            # 为天气相关传感器添加详细属性
            today_data = self._get_day_forecast(daily_forecast, 0)
            if today_data and sensor_key.startswith("today_"):
                attributes.update({
                    "天气数据来源": api_source.get("weather_api", "未知"),
                    "日出时间": today_data.get('sunrise', '未知'),
                    "日落时间": today_data.get('sunset', '未知'),
                    "气压": f"{today_data.get('pressure', '未知')}hPa",
                    "能见度": f"{today_data.get('vis', '未知')}km",
                    "云量": f"{today_data.get('cloud', '未知')}%",
                    "月相": today_data.get('moonPhase', '未知'),
                    "白天天气图标": today_data.get('iconDay', '未知'),
                    "夜间天气图标": today_data.get('iconNight', '未知'),
                    "夜间天气": today_data.get('textNight', '未知'),
                    "白天天气": today_data.get('textDay', '未知')
                })
            
            tomorrow_data = self._get_day_forecast(daily_forecast, 1)
            if tomorrow_data and sensor_key.startswith("tomorrow_"):
                attributes.update({
                    "天气数据来源": api_source.get("weather_api", "未知"),
                    "日出时间": tomorrow_data.get('sunrise', '未知'),
                    "日落时间": tomorrow_data.get('sunset', '未知'),
                    "白天天气": tomorrow_data.get('textDay', '未知'),
                    "夜间天气": tomorrow_data.get('textNight', '未知')
                })
            
            day3_data = self._get_day_forecast(daily_forecast, 2)
            if day3_data and sensor_key.startswith("day3_"):
                attributes.update({
                    "天气数据来源": api_source.get("weather_api", "未知"),
                    "日出时间": day3_data.get('sunrise', '未知'),
                    "日落时间": day3_data.get('sunset', '未知'),
                    "白天天气": day3_data.get('textDay', '未知'),
                    "夜间天气": day3_data.get('textNight', '未知')
                })
    
            _LOGGER.error("[天气服务] 传感器 %s 属性获取成功", sensor_key)
            return attributes
    
        except Exception as e:
            _LOGGER.error("[天气服务] 获取传感器属性失败: %s", str(e), exc_info=True)
            return {}

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        _LOGGER.error("[天气服务] 开始验证配置")
        required_fields = ["private_key", "project_id", "key_id"]
        for field in required_fields:
            if not config.get(field):
                error_msg = f"必须提供{field}"
                _LOGGER.error("[天气服务] 配置验证失败: %s", error_msg)
                raise ValueError(error_msg)
        
        # 验证私钥格式
        private_key = config.get("private_key", "").strip()
        if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
            error_msg = "私钥格式不正确，必须是PEM格式"
            _LOGGER.error("[天气服务] 配置验证失败: %s", error_msg)
            raise ValueError(error_msg)
        
        _LOGGER.error("[天气服务] 配置验证成功")