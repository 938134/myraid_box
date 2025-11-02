from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, Tuple, Union
from datetime import timedelta, datetime
import logging
import aiohttp
import time

_LOGGER = logging.getLogger(__name__)

class AttributeConfig(TypedDict, total=False):
    """传感器属性配置类型定义"""
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    value_map: Dict[str, str] | None

class SensorConfig(TypedDict, total=False):
    """传感器配置类型定义"""
    key: str
    name: str
    icon: str
    unit: str | None
    device_class: str | None
    entity_category: str | None
    value_formatter: str | None
    sort_order: int  # 新增：实体创建顺序
    is_attribute: bool  # 新增：标记是否为属性传感器
    parent_sensor: str  # 新增：父传感器key

class BaseService(ABC):
    """增强的服务基类 - 支持自动配置、实体排序和Token认证"""

    # 类常量
    DEFAULT_UPDATE_INTERVAL = 10  # 默认更新间隔（分钟）
    DEFAULT_API_URL = ""  # 子类需要覆盖这个

    def __init__(self):
        """初始化服务实例"""
        self._last_update: datetime | None = None
        self._last_successful: bool = True
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expiry: float | None = None

    @property
    @abstractmethod
    def service_id(self) -> str:
        """返回服务的唯一标识符"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回服务的用户友好名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """返回服务的详细描述"""

    @property
    def config_help(self) -> str:
        """返回服务的配置说明 - 子类可覆盖"""
        return f"配置 {self.name} 的相关参数"

    @property
    def device_name(self) -> str:
        """返回设备名称"""
        return self.name

    @property
    def icon(self) -> str:
        """返回服务的默认图标"""
        return "mdi:information"

    @property
    def default_update_interval(self) -> timedelta:
        """从config_fields获取默认更新间隔"""
        interval_minutes = int(self.config_fields.get("interval", {}).get("default", self.DEFAULT_UPDATE_INTERVAL))
        return timedelta(minutes=interval_minutes)

    @property
    def default_api_url(self) -> str:
        """返回默认API地址"""
        return self.DEFAULT_API_URL

    @property
    @abstractmethod
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """抽象方法：返回服务的配置字段定义"""

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回该服务提供的所有传感器配置（已排序）"""
        configs = self._get_sensor_configs()
        # 按 sort_order 排序，如果没有设置则按添加顺序
        return sorted(configs, key=lambda x: x.get('sort_order', 999))

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """子类实现的具体传感器配置"""
        return []

    def get_attribute_configs(self, parent_sensor_key: str) -> List[SensorConfig]:
        """获取指定父传感器的属性传感器配置"""
        return []

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据传感器key获取对应的值"""
        if not data or data.get("status") != "success":
            return None
            
        parsed_data = self.parse_response(data)
        return parsed_data.get(sensor_key)

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        if value is None:
            return "暂无数据"
        return str(value)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        return {}

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器的动态图标 - 子类可覆盖此方法实现动态图标"""
        # 默认返回传感器配置中的图标
        sensor_config = next((config for config in self.sensor_configs if config["key"] == sensor_key), None)
        if sensor_config and sensor_config.get("icon"):
            return sensor_config["icon"]
        return "mdi:information"

    async def async_unload(self) -> None:
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("[%s] HTTP会话已关闭", self.service_id)

    async def _ensure_session(self) -> None:
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def _ensure_token(self, params: Dict[str, Any]) -> str:
        """确保有有效的token - 子类可覆盖实现具体token获取逻辑"""
        # 检查token是否仍然有效（如果有过期时间）
        if self._token and self._token_expiry and time.time() < self._token_expiry:
            return self._token
            
        # 默认实现：从参数中获取token或生成新token
        token = params.get("token") or params.get("access_token")
        if token:
            self._token = token
            # 默认token有效期为1小时
            self._token_expiry = time.time() + 3600
            return token
            
        return ""

    def _build_request_headers(self, token: str = "") -> Dict[str, str]:
        """构建请求头 - 包含基础headers和认证headers"""
        # 基础headers
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "application/json"
        }
        
        # 添加认证headers（如果有token）
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        return headers

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据（网络请求和数据获取）- 支持GET和POST请求"""
        await self._ensure_session()
        try:
            # 确保有有效的token
            token = await self._ensure_token(params)
            
            url, request_data, headers = self.build_request(params, token)
            
            # 判断是GET还是POST请求
            use_post = isinstance(request_data, dict) and not any(key in request_data for key in ['params', 'data', 'json'])
            
            if use_post:
                # POST请求 - request_data 作为JSON数据
                async with self._session.post(url, json=request_data, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                # GET请求 - request_data 作为查询参数
                async with self._session.get(url, params=request_data, headers=headers) as resp:
                    return await self._handle_response(resp)
                    
        except Exception as e:
            _LOGGER.error("[%s] 请求失败: %s", self.service_id, str(e), exc_info=True)
            return {
                "data": None,
                "status": "error",
                "error": str(e),
                "update_time": datetime.now().isoformat()
            }

    async def _handle_response(self, resp) -> Dict[str, Any]:
        """处理HTTP响应"""
        content_type = resp.headers.get("Content-Type", "").lower()
        resp.raise_for_status()
        
        if "application/json" in content_type:
            data = await resp.json()
        else:
            data = await resp.text()
        
        return {
            "data": data,
            "status": "success",
            "error": None,
            "update_time": datetime.now().isoformat()
        }

    def build_request(self, params: Dict[str, Any], token: str = "") -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求的 URL、参数和请求头 - 支持Token认证"""
        url = self.default_api_url
        request_params = self._build_request_params(params)
        headers = self._build_request_headers(token)
        
        return url, request_params, headers

    def _build_request_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求参数 - 子类可覆盖"""
        return {}

    @abstractmethod
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        pass

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置 - 子类可覆盖"""
        pass

    def _create_sensor_config(self, key: str, name: str, icon: str, 
                            unit: str = None, device_class: str = None, 
                            sort_order: int = 999, is_attribute: bool = False,
                            parent_sensor: str = None) -> SensorConfig:
        """快速创建传感器配置的辅助方法"""
        return {
            "key": key,
            "name": name,
            "icon": icon,
            "unit": unit,
            "device_class": device_class,
            "sort_order": sort_order,
            "is_attribute": is_attribute,
            "parent_sensor": parent_sensor
        }

    def _generate_jwt_token(self, private_key: str, payload: Dict[str, Any], 
                          headers: Dict[str, Any] = None) -> str:
        """生成JWT令牌的通用方法"""
        try:
            import jwt
            return jwt.encode(payload, private_key, algorithm='EdDSA', headers=headers)
        except ImportError:
            _LOGGER.error("jwt库未安装，无法生成JWT令牌")
            raise
        except Exception as e:
            _LOGGER.error("生成JWT令牌失败: %s", str(e))
            raise

    def _validate_jwt_payload(self, payload: Dict[str, Any]) -> None:
        """验证JWT payload的基本字段"""
        required_fields = ['iat', 'exp']
        for field in required_fields:
            if field not in payload:
                raise ValueError(f"JWT payload必须包含{field}字段")