"""每日天气服务（和风天气，JWT 认证）。

设计要点：
- 单一 service 文件，与 ``history.py`` / ``oil.py`` / ``poetry.py`` /
  ``hitokoto.py`` / ``istoreos.py`` 保持并列的 services/*.py 结构，
  方便 ``services`` 目录被 ``const.SERVICE_REGISTRY`` 静态引用，
  也符合 HACS / Home Assistant 集成常见目录布局。
- 模块内的"纯格式化函数"（``format_temperature`` / ``format_weather_text``
  / ``format_wind_text`` / ``format_future_weather`` / ``format_today_detail``
  / ``format_sensor_value`` / ``build_sensor_attributes`` 等）不依赖 self，
  可以直接 ``from custom_components.myraid_box.services.weather import format_xxx``
  做单测和复用；``WeatherService`` 类只保留"编排"逻辑：JWT 生成、
  API 请求、响应装配、config schema。
- 传感器格式化函数集中在此文件末尾，方便阅读；如需国际化，可整体搬到
  独立的 ``weather_formatters.py`` 并从这里 import，属于下一步优化。
"""
from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional

import jwt

from ..service_base import BaseService, RequestConfig, SensorConfig

_LOGGER = logging.getLogger(__name__)


# ============================================================
# 纯格式化函数（无 self 依赖，方便单测和国际化）
# ============================================================

def get_day_forecast(
    daily_forecast: Optional[List[Dict]],
    index: int,
) -> Optional[Dict]:
    """安全获取某天预报数据。越界/类型错误返回 None，不抛异常。"""
    try:
        if not daily_forecast or not isinstance(daily_forecast, list):
            return None
        return daily_forecast[index] if index < len(daily_forecast) else None
    except (IndexError, TypeError, AttributeError):
        return None


def format_temperature(temp_min: Any, temp_max: Any) -> str:
    """格式化温度显示：``18~26°C``、``22°C``、``未知``。"""
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


def format_weather_text(weather_day: str, weather_night: str) -> str:
    """格式化天气文本：白天/夜间分别描述；相同则只说一次。"""
    if not weather_day or not weather_night:
        return weather_day or weather_night or "未知"
    if weather_day == weather_night:
        return weather_day
    return f"白天{weather_day}，夜间{weather_night}"


def format_wind_text(
    wind_dir_day: str,
    wind_scale_day: str,
    wind_dir_night: str,
    wind_scale_night: str,
) -> str:
    """格式化风力文本：白天/夜间分别描述；相同则只说一次。"""
    day_wind = (
        f"{wind_dir_day}{wind_scale_day}级" if wind_dir_day and wind_scale_day else ""
    )
    night_wind = (
        f"{wind_dir_night}{wind_scale_night}级"
        if wind_dir_night and wind_scale_night
        else ""
    )
    if not day_wind and not night_wind:
        return "未知"
    if not day_wind:
        return night_wind
    if not night_wind:
        return day_wind
    if day_wind == night_wind:
        return day_wind
    return f"白天{day_wind}，夜间{night_wind}"


def format_future_weather(weather_data: Optional[Dict]) -> str:
    """格式化未来某天的完整天气：``白天晴，夜间多云，18~26°C，东风3级``。"""
    if not weather_data:
        return "暂无数据"

    weather_text = format_weather_text(
        weather_data.get("textDay", ""),
        weather_data.get("textNight", ""),
    )
    temp_str = format_temperature(
        weather_data.get("tempMin"),
        weather_data.get("tempMax"),
    )
    wind_text = format_wind_text(
        weather_data.get("windDirDay", ""),
        weather_data.get("windScaleDay", ""),
        weather_data.get("windDirNight", ""),
        weather_data.get("windScaleNight", ""),
    )
    return f"{weather_text}，{temp_str}，{wind_text}"


def format_today_detail(today_data: Dict[str, Any]) -> str:
    """格式化今日详情：温度/湿度/风力 + 温馨提醒。"""
    if not today_data:
        return "暂无数据"

    weather_text = format_weather_text(
        today_data.get("textDay", ""),
        today_data.get("textNight", ""),
    )
    temp_str = format_temperature(
        today_data.get("tempMin"),
        today_data.get("tempMax"),
    )
    humidity = today_data.get("humidity", "未知")
    humidity_str = f"{humidity}%" if humidity != "未知" else "未知"
    wind_text = format_wind_text(
        today_data.get("windDirDay", ""),
        today_data.get("windScaleDay", ""),
        today_data.get("windDirNight", ""),
        today_data.get("windScaleNight", ""),
    )

    # 温馨提醒：雨天/雪天
    day_weather = today_data.get("textDay", "").lower()
    reminders: List[str] = []
    rain_words = ("雨", "雪", "雷", "storm", "rain", "snow", "thunder")
    if any(word in day_weather for word in rain_words):
        reminders.append("记得携带雨具，保持干爽")

    # 紫外线
    uv_index = today_data.get("uvIndex")
    if uv_index is not None and isinstance(uv_index, (int, str)):
        try:
            uv_value = int(uv_index)
            if uv_value >= 6:
                reminders.append("紫外线强烈，建议做好防晒保护")
            elif uv_value >= 3:
                reminders.append("紫外线适中，外出请注意防护")
        except (ValueError, TypeError):
            pass

    # 极端温度
    try:
        temp_max = today_data.get("tempMax")
        if temp_max is not None and int(temp_max) >= 30:
            reminders.append("天气炎热，注意防暑降温")
        elif temp_max is not None and int(temp_max) <= 5:
            reminders.append("天气寒冷，注意添衣保暖")
    except (ValueError, TypeError):
        pass

    detail_parts = [
        weather_text,
        f"温度{temp_str}",
        f"湿度{humidity_str}",
        f"风力{wind_text}",
    ]

    if reminders:
        detail_parts.append(f"温馨提醒：{'；'.join(reminders)}")
    else:
        detail_parts.append("天气宜人，愿您享受美好时光")

    return "，".join(detail_parts)


# ============================================================
# 传感器默认值 & 值分派
# ============================================================

_NUMERIC_SENSORS = frozenset(
    {"today_humidity", "today_precip", "today_pressure", "today_vis", "today_cloud"}
)

_TEXT_DEFAULTS = {
    "city_name": "加载中...",
    "today_weather": "加载中...",
    "today_temp": "加载中...",
    "today_wind": "加载中...",
    "today_uv": "加载中...",
    "tomorrow_weather": "加载中...",
    "day3_weather": "加载中...",
}


def get_sensor_default(sensor_key: str) -> Any:
    """获取传感器默认值。数值型返回 None，文本型返回加载提示。"""
    if sensor_key in _NUMERIC_SENSORS:
        return None
    return _TEXT_DEFAULTS.get(sensor_key, "加载中...")


def format_sensor_value(sensor_key: str, data: Any) -> Any:
    """根据 sensor_key 从数据里抽取并格式化对应值。"""
    if not data or data.get("status") != "success":
        return get_sensor_default(sensor_key)

    data_content = data.get("data") or {}
    city_info = data_content.get("city_info") or {}
    daily_forecast = data_content.get("daily_forecast") or []

    day0 = get_day_forecast(daily_forecast, 0)  # 今天
    day1 = get_day_forecast(daily_forecast, 1)  # 明天
    day2 = get_day_forecast(daily_forecast, 2)  # 后天

    handlers = {
        # 城市信息
        "city_name": lambda: city_info.get("name", "未知"),
        # 今日天气
        "today_weather": lambda: (
            format_weather_text(
                day0.get("textDay", ""),
                day0.get("textNight", ""),
            )
            if day0
            else "暂无数据"
        ),
        "today_temp": lambda: (
            format_temperature(day0.get("tempMin"), day0.get("tempMax"))
            if day0
            else "未知"
        ),
        "today_humidity": lambda: day0.get("humidity") if day0 else None,
        "today_wind": lambda: (
            format_wind_text(
                day0.get("windDirDay", ""),
                day0.get("windScaleDay", ""),
                day0.get("windDirNight", ""),
                day0.get("windScaleNight", ""),
            )
            if day0
            else "未知"
        ),
        "today_precip": lambda: day0.get("precip") if day0 else None,
        "today_pressure": lambda: day0.get("pressure") if day0 else None,
        "today_vis": lambda: day0.get("vis") if day0 else None,
        "today_cloud": lambda: day0.get("cloud") if day0 else None,
        "today_uv": lambda: (
            f"{day0.get('uvIndex', '未知')}级" if day0 else "未知"
        ),
        # 未来天气
        "tomorrow_weather": lambda: format_future_weather(day1),
        "day3_weather": lambda: format_future_weather(day2),
    }

    handler = handlers.get(sensor_key)
    if handler:
        try:
            return handler()
        except Exception:
            return get_sensor_default(sensor_key)
    return get_sensor_default(sensor_key)


# ============================================================
# 传感器属性
# ============================================================

def build_sensor_attributes(sensor_key: str, data: Any) -> Dict[str, Any]:
    """获取传感器的额外属性。"""
    if not data or data.get("status") != "success":
        return {}

    try:
        data_content = data.get("data") or {}
        city_info = data_content.get("city_info") or {}
        daily_forecast = data_content.get("daily_forecast") or []
        api_source = data_content.get("api_source") or {}

        attributes: Dict[str, Any] = {
            "数据来源": api_source.get("city_api", "未知"),
            "天气数据来源": api_source.get("weather_api", "未知"),
            "JWT状态": data_content.get("jwt_status", "未知"),
            "更新时间": data_content.get("update_time", "未知"),
        }

        # 城市名称传感器专属属性
        if sensor_key == "city_name":
            attributes.update(
                {
                    "城市ID": city_info.get("id", "未知"),
                    "国家": city_info.get("country", "未知"),
                    "省份": city_info.get("adm1", "未知"),
                    "地区": city_info.get("adm2", "未知"),
                    "城市经度": city_info.get("lon", "未知"),
                    "城市纬度": city_info.get("lat", "未知"),
                    "时区": city_info.get("tz", "未知"),
                }
            )

        # 3 天天气传感器共享的属性
        day_mapping = {
            "today_weather": 0,
            "tomorrow_weather": 1,
            "day3_weather": 2,
        }
        if sensor_key in day_mapping:
            day_data = get_day_forecast(daily_forecast, day_mapping[sensor_key])
            if day_data:
                attributes.update(
                    {
                        "日出": day_data.get("sunrise", "未知"),
                        "日落": day_data.get("sunset", "未知"),
                        "月相": day_data.get("moonPhase", "未知"),
                        "白天天气": day_data.get("textDay", "未知"),
                        "夜间天气": day_data.get("textNight", "未知"),
                        "最低温度": day_data.get("tempMin", "未知"),
                        "最高温度": day_data.get("tempMax", "未知"),
                        "湿度": day_data.get("humidity", "未知"),
                        "紫外线指数": day_data.get("uvIndex", "未知"),
                    }
                )
                if sensor_key == "today_weather":
                    attributes["详情"] = format_today_detail(day_data)

        return attributes
    except Exception:
        return {}


# ============================================================
# WeatherService（编排层：JWT / API / config schema）
# ============================================================

class WeatherService(BaseService):
    """每日天气服务 - 使用新版基类。

    主要职责：
    - JWT 认证（EdDSA 签名，15 分钟 TTL）
    - 两步 API 请求（城市查询 + 天气详情）
    - 响应装配（合并城市、天气、API 来源、更新时间）
    - 传感器配置声明

    传感器值 / 属性的**纯函数格式化**已抽到本模块的模块级函数
    （``format_sensor_value`` / ``build_sensor_attributes`` 等），
    ``WeatherService`` 上的同名 public 方法只是**薄 wrapper**，
    保留是为了兼容 ``BaseService`` 抽象方法签名和外部调用点。
    """

    DEFAULT_API_URL = "https://devapi.qweather.com"
    DEFAULT_UPDATE_INTERVAL = 30
    DEFAULT_TIMEOUT = 60  # 天气 API 可能较慢

    def __init__(self, hass=None):
        super().__init__(hass=hass)
        self._current_city_id = None

    # ------------------------------------------------------------
    # 元数据（服务基本信息）
    # ------------------------------------------------------------
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
        return (
            "🌤️ 天气服务配置说明：\n"
            "1. 注册和风天气开发者账号：https://dev.qweather.com/\n"
            "2. 创建项目获取项目ID、密钥ID和EdDSA私钥\n"
            "3. 城市名称支持中文、拼音或LocationID"
        )

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
                "description": "更新间隔时间（分钟）",
            },
            "location": {
                "name": "城市名称",
                "type": "str",
                "default": "beij",
                "description": "城市名称或拼音（如：beij, shanghai）",
            },
            "api_host": {
                "name": "API主机",
                "type": "str",
                "default": "https://devapi.qweather.com",
                "description": "天气API服务地址",
            },
            "private_key": {
                "name": "私钥",
                "type": "password",
                "default": "",
                "description": "EdDSA私钥（PEM格式）",
            },
            "project_id": {
                "name": "项目ID",
                "type": "str",
                "default": "PROJECT_ID",
                "description": "项目标识符",
            },
            "key_id": {
                "name": "密钥ID",
                "type": "str",
                "default": "KEY_ID",
                "description": "密钥标识符",
            },
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日天气服务的传感器配置。"""
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

    # ------------------------------------------------------------
    # Token（JWT 生成，走基类 _ensure_token 的锁）
    # ------------------------------------------------------------
    async def _refresh_token(self, params: Dict[str, Any]) -> str:
        """生成和风天气JWT token（基类负责加锁 + 缓存 + TTL 判定）。

        约定：
        - JWT 有效期 15 分钟，通过设置 ``self._token_expiry`` 显式告诉
          基类"用 JWT 自带的 exp，而不是 DEFAULT_TOKEN_TTL"。
        - 生成失败返回 ""，让基类统一兜底。
        """
        private_key = params.get("private_key", "").strip()
        project_id = params.get("project_id", "YOUR_PROJECT_ID")
        key_id = params.get("key_id", "YOUR_KEY_ID")

        if not private_key:
            _LOGGER.error("天气服务私钥未配置")
            return ""

        payload = {
            "iat": int(time.time()) - 30,  # 容忍 30 秒时钟漂移
            "exp": int(time.time()) + 900,  # 15 分钟有效期
            "sub": project_id,
        }

        try:
            token = jwt.encode(
                payload, private_key, algorithm="EdDSA", headers={"kid": key_id}
            )
            # 显式告诉基类用 JWT 自带的 exp（略提前 60s，避免刚好到期时请求）
            self._token_expiry = payload["exp"] - 60
            _LOGGER.debug("成功生成天气JWT令牌")
            return token
        except Exception as e:
            _LOGGER.error("生成天气JWT令牌失败: %s", e)
            return ""

    # ------------------------------------------------------------
    # HTTP 请求
    # ------------------------------------------------------------
    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建天气API请求 - 城市查询"""
        api_host = params.get("api_host", self.default_api_url).rstrip("/")
        location = params.get("location", "beij")

        url = f"{api_host}/geo/v2/city/lookup"

        return RequestConfig(
            url=url,
            method="GET",
            params={"location": location},
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
                "update_time": datetime.now().isoformat(),
            }

        except Exception as e:
            _LOGGER.error(
                "[天气服务] 获取天气数据失败: %s", str(e), exc_info=True
            )
            return self._create_error_response(str(e))

    async def _fetch_weather_data(
        self, params: Dict[str, Any], city_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取天气数据"""
        try:
            city_info = ((city_data.get("location", []) or [{}])[0])
            city_id = city_info.get("id")

            if not city_id:
                return self._create_weather_response(city_info, {}, "城市ID无效")

            api_host = params.get("api_host", self.default_api_url).rstrip("/")
            weather_url = f"{api_host}/v7/weather/3d"

            # 获取 token
            token = await self._ensure_token(params)
            if not token:
                return self._create_weather_response(city_info, {}, "JWT令牌无效")

            # 构建天气请求头 - 使用基类的 _build_auth_headers
            headers = self._build_auth_headers(token)

            async with self._session.get(
                weather_url,
                params={"location": city_id},
                headers=headers,
            ) as resp:
                if resp.status == 401:
                    return self._create_weather_response(
                        city_info, {}, "天气API认证失败"
                    )

                resp.raise_for_status()
                weather_response = await resp.json()

                if weather_response.get("code") != "200":
                    error_msg = weather_response.get(
                        "message", "天气数据获取失败"
                    )
                    return self._create_weather_response(
                        city_info, {}, f"天气API错误: {error_msg}"
                    )

                return self._create_weather_response(
                    city_info,
                    city_data.get("refer", {}),
                    "有效",
                    weather_data=weather_response,
                    daily_forecast=weather_response.get("daily", []),
                    weather_api=weather_response.get("refer", {}).get(
                        "sources", ["未知"]
                    )[0],
                    update_time=weather_response.get("updateTime", "未知"),
                )

        except Exception as e:
            _LOGGER.error("[天气服务] 获取天气数据失败: %s", str(e))
            city_info = ((city_data.get("location", []) or [{}])[0])
            return self._create_weather_response(
                city_info,
                city_data.get("refer", {}),
                f"获取失败: {str(e)}",
            )

    def _create_weather_response(
        self,
        city_info: Dict,
        city_api: Dict,
        jwt_status: str,
        weather_data: Optional[Dict] = None,
        daily_forecast: Optional[List] = None,
        weather_api: str = "未知",
        update_time: str = "未知",
    ) -> Dict[str, Any]:
        """创建天气数据响应"""
        return {
            "city_info": city_info,
            "weather_data": weather_data or {},
            "daily_forecast": daily_forecast or [],
            "api_source": {
                "city_api": city_api.get("sources", ["未知"])[0],
                "weather_api": weather_api,
            },
            "update_time": update_time,
            "jwt_status": jwt_status,
        }

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析城市查询响应数据"""
        if not isinstance(response_data, dict):
            return {
                "status": "error",
                "error": "无效的响应格式",
            }

        # 检查API返回码
        code = response_data.get("code")
        if code != "200":
            error_msg = response_data.get("message", "未知错误")
            return {
                "status": "error",
                "error": f"城市查询失败: {error_msg}",
            }

        return response_data

    def _create_error_response(
        self, error_msg: str, error_type: str = "error"
    ) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "data": None,
            "status": error_type,
            "error": error_msg,
            "update_time": datetime.now().isoformat(),
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

    # ------------------------------------------------------------
    # 传感器值 / 属性 —— 薄 wrapper，实际实现是模块级纯函数
    # ------------------------------------------------------------
    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """转发到模块级 ``format_sensor_value``。"""
        return format_sensor_value(sensor_key, data)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """转发到模块级 ``build_sensor_attributes``，再合并基类通用属性。"""
        base_attrs = super().get_sensor_attributes(sensor_key, data)
        result = build_sensor_attributes(sensor_key, data)
        result.update(base_attrs)
        return result
