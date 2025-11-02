
from typing import Dict, Any, List, Tuple
from datetime import datetime
import logging
import aiohttp
import json
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class IStoreOSService(BaseService):
    """多传感器版 iStoreOS 固件版本服务 - 支持动态图标"""

    DEFAULT_API_URL = "https://fwindex.koolcenter.com/api/fw/device"
    DEFAULT_UPDATE_INTERVAL = 300  # 5分钟
    
    # 设备型号映射
    DEVICE_MAP = {
        "seed-ac1": "Seed AC1",
        "seed-ac2": "Seed AC2", 
        "seed-ac3": "Seed AC3",
        "r2s": "R2S",
        "r3s": "R3S",
        "r4s": "R4S",
        "r4s-1g": "R4S 1G",
        "r4se": "R4SE",
        "r5s": "R5S",
        "r6s": "R6S",
        "r6xs": "R6XS",
        "r66s": "R66S",
        "r68s": "R68S",
        "r76s": "R76S",
        "rpi4": "Raspberry Pi 4",
        "rpi5": "Raspberry Pi 5",
        "x86_64": "X86_64",
        "x86_64_efi": "X86_64 EFI",
        "t68m": "T68M",
        "station-p2": "Station P2",
        "mt3000": "MT3000",
        "h28k": "H28K",
        "h88k": "H88K",
        "h6xk": "H6XK",
        "e20c": "E20C",
        "e52c": "E52C",
        "e54c": "E54C",
        "easepi-r1": "EasePi R1",
        "easepi-r1-lite": "EasePi R1 Lite",
        "gl-be3600": "GL-BE3600",
        "ars2": "ARS2",
        "ars4": "ARS4",
        "ala2": "AL A2",
        "alpha": "Alpha",
        "zx3000": "ZX3000",
        "armsr": "ARM SR",
        "ib": "IB",
        "p2pro": "P2 Pro",
        "Virtual": "Virtual"
    }

    def __init__(self):
        super().__init__()
        self._current_device = "seed-ac2"  # 存储当前设备

    @property
    def service_id(self) -> str:
        return "istoreos"

    @property
    def name(self) -> str:
        return "iStoreOS版本"

    @property
    def description(self) -> str:
        return "获取iStoreOS设备固件版本信息"

    @property
    def icon(self) -> str:
        return "mdi:package-variant"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "device_name": {
                "name": "设备型号",
                "type": "select",
                "default": "seed-ac2",
                "description": "选择设备型号",
                "options": sorted(self.DEVICE_MAP.keys(), key=lambda x: self.DEVICE_MAP[x])
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回iStoreOS版本服务的传感器配置"""
        return [
            self._create_sensor_config("device_name", "设备", "mdi:devices", None, None, 1),
            self._create_sensor_config("latest_version", "最新版本", "mdi:tag", None, None, 2),
            self._create_sensor_config("release_count", "数量", "mdi:counter", "个", None, 3),
        ]

    def build_request(self, params: Dict[str, Any], token: str = "") -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建POST请求参数"""
        device_name = params.get("device_name", "seed-ac2")
        self._current_device = device_name  # 保存当前设备
        
        # 构建POST请求数据
        post_data = {
            "deviceName": device_name,
            "firmwareName": "iStoreOS"
        }
        
        url = self.DEFAULT_API_URL
        headers = self._build_request_headers(token)
        
        return url, post_data, headers

    def _build_request_headers(self, token: str = "") -> Dict[str, str]:
        """构建请求头 - iStoreOS需要JSON内容类型"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "application/json"
        }
        
        # 如果有token，添加到headers
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        return headers

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以支持POST请求"""
        await self._ensure_session()
        try:
            # 获取token并构建请求
            token = await self._ensure_token(params)
            url, post_data, headers = self.build_request(params, token)
            
            async with self._session.post(
                url, 
                json=post_data, 
                headers=headers
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                # 直接解析数据，返回给协调器
                return self.parse_response({
                    "data": data,
                    "status": "success",
                    "error": None,
                    "update_time": datetime.now().isoformat()
                })
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("[iStoreOS] 网络请求失败: %s", str(e), exc_info=True)
            return self._create_error_response(f"网络错误: {str(e)}")
        except Exception as e:
            _LOGGER.error("[iStoreOS] 请求失败: %s", str(e), exc_info=True)
            return self._create_error_response(str(e))

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析API响应数据"""
        try:
            # 处理基类返回的数据结构
            if isinstance(response_data, dict) and "data" in response_data:
                api_data = response_data["data"]
                update_time = response_data.get("update_time", datetime.now().isoformat())
            else:
                api_data = response_data
                update_time = datetime.now().isoformat()

            # 检查API响应状态
            if not api_data or not api_data.get("result"):
                return self._create_error_response("API返回数据无效", update_time)

            result = api_data["result"]
            
            # 正确的数据结构路径：result['device']['cover']
            device_data = result.get("device", {})
            releases = result.get("releases", [])
            
            # 获取最新版本
            latest_release = releases[0] if releases else {}
            latest_version = latest_release.get("release", "未知")
            
            # 获取设备显示名称 - 使用保存的设备名称
            device_display_name = self.DEVICE_MAP.get(
                self._current_device, 
                self._current_device
            )

            # 获取设备封面图片URL
            device_cover = device_data.get("cover", "")
            
            return {
                "status": "success",
                "device_name": device_display_name,
                "latest_version": latest_version,
                "device_cover": device_cover,
                "release_count": len(releases),
                "firmware_name": "iStoreOS",
                "update_time": update_time
            }
            
        except Exception as e:
            _LOGGER.error("[iStoreOS] 解析响应数据时发生异常: %s", str(e), exc_info=True)
            return self._create_error_response(f"解析错误: {str(e)}", datetime.now().isoformat())

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """根据传感器key获取对应的值"""
        if not data or data.get("status") != "success":
            return None
            
        return data.get(sensor_key)

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        if not data or data.get("status") != "success":
            return self._get_default_value(sensor_key, "数据加载中")
            
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_default_value(sensor_key, "暂无数据")
            
        # 为不同传感器提供特定的格式化
        formatters = {
            "device_name": self._format_device_name,
            "latest_version": self._format_version,
            "release_count": self._format_count
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_device_name(self, value: str) -> str:
        """格式化设备名称"""
        return value if value and value != "未知" else "未知设备"

    def _format_version(self, value: str) -> str:
        """格式化版本号"""
        return value if value and value != "unknown" else "未知版本"

    def _format_count(self, value: int) -> str:
        """格式化数量"""
        return f"{value}" if value else "0"

    def _get_default_value(self, sensor_key: str, default: str) -> Any:
        """获取传感器默认值"""
        numeric_sensors = ["release_count"]
        return None if sensor_key in numeric_sensors else default

    def _create_error_response(self, error_msg: str, update_time: str = None) -> Dict[str, Any]:
        """创建错误响应"""
        if update_time is None:
            update_time = datetime.now().isoformat()
            
        return {
            "status": "error",
            "device_name": "未知",
            "latest_version": "未知",
            "device_cover": "",
            "release_count": 0,
            "update_time": update_time,
            "error": error_msg
        }

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        if not data or data.get("status") != "success":
            return {}
            
        attributes = {
            "更新时间": data.get("update_time", "未知"),
            "数据状态": "成功"
        }
        
        return attributes

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器的动态图标"""
        # 默认返回配置的图标
        default_icon = "mdi:devices" if sensor_key == "device_name" else "mdi:tag"
        
        if not data or data.get("status") != "success":
            return default_icon
            
        # 对于设备名称传感器，如果有设备封面图片，使用图片URL作为图标
        if sensor_key == "device_name":
            device_cover = data.get("device_cover", "")
            if device_cover and device_cover.startswith(('http://', 'https://')):
                return device_cover
                
        return default_icon

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        device_name = config.get("device_name")
        if not device_name:
            raise ValueError("必须选择设备型号")
        
        if device_name not in cls.DEVICE_MAP:
            raise ValueError(f"不支持的设备型号: {device_name}")