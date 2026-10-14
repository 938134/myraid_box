from typing import Dict, Any, List
from datetime import datetime
import logging
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class IStoreOSService(BaseService):
    """iStoreOS固件服务 - 使用新版基类"""

    DEFAULT_API_URL = "https://fwindex.koolcenter.com/api/fw/device"
    DEFAULT_UPDATE_INTERVAL = 300  # 5分钟
    DEFAULT_TIMEOUT = 30

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

    def __init__(self, hass=None):
        super().__init__(hass=hass)
        self._current_device = "seed-ac2"  # 存储当前设备

    @property
    def service_id(self) -> str:
        return "istoreos"

    @property
    def name(self) -> str:
        return "iStoreOS固件"  # 更新名称

    @property
    def description(self) -> str:
        return "获取iStoreOS设备固件版本信息"

    @property
    def config_help(self) -> str:
        return "🔄 iStoreOS固件服务配置说明：\n1. 选择设备型号\n2. 自动检查固件更新\n3. 显示最新版本信息"

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
        """返回iStoreOS固件服务的传感器配置"""
        return [
            self._create_sensor_config("device_name", "设备", "mdi:devices", None, "camera"), 
            self._create_sensor_config("latest_version", "最新版本", "mdi:tag"),
            self._create_sensor_config("release_count", "固件数量", "mdi:counter", "个"),
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建iStoreOS API请求"""
        device_name = params.get("device_name", "seed-ac2")
        self._current_device = device_name  # 保存当前设备
        
        # 构建POST请求数据
        post_data = {
            "deviceName": device_name,
            "firmwareName": "iStoreOS"
        }
        
        return RequestConfig(
            url=self.default_api_url,
            method="POST",
            json_data=post_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析iStoreOS API响应数据"""
        if not isinstance(response_data, dict):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        # 检查API响应状态
        if not response_data.get("result"):
            return {
                "status": "error",
                "error": "API返回数据无效"
            }

        try:
            result = response_data["result"]
            device_data = result.get("device", {})
            releases = result.get("releases", [])
            
            # 获取最新版本
            latest_release = releases[0] if releases else {}
            latest_version = latest_release.get("release", "未知")
            
            # 获取设备显示名称
            device_display_name = self.DEVICE_MAP.get(
                self._current_device, 
                self._current_device
            )

            # 获取设备封面图片URL
            device_cover = device_data.get("cover", "")
            
            return {
                "device_name": device_display_name,
                "latest_version": latest_version,
                "device_cover": device_cover,
                "release_count": len(releases),
                "firmware_name": "iStoreOS"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"解析数据失败: {str(e)}"
            }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        if sensor_key == "device_name":
            # 对于 camera device_class，返回设备名称作为显示值
            if data and data.get("status") == "success":
                parsed_data = data.get("data", {})
                return parsed_data.get("device_name", "未知设备")
            return "加载中..."
        
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
            
        # 对固件数量进行特殊处理
        if sensor_key == "release_count":
            return value  # 返回数值
            
        return super().format_sensor_value(sensor_key, data)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        parsed_data = data.get("data", {})
        
        # 为设备传感器添加完整信息
        if sensor_key == "device_name":
            device_cover = parsed_data.get("device_cover", "")
            attributes.update({
                "设备型号": self._current_device,
                "最新版本": parsed_data.get("latest_version", "未知"),
                "固件数量": parsed_data.get("release_count", 0),
                "固件名称": parsed_data.get("firmware_name", "iStoreOS"),
                "设备封面": device_cover,
                "数据来源": "koolcenter.com"
            })
            
            # 设置 entity_picture 用于显示图片
            if device_cover:
                attributes["entity_picture"] = device_cover
        
        return attributes

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器的动态图标"""
        # 对于 camera device_class 的传感器，不需要返回图标
        if sensor_key == "device_name":
            return ""  # 返回空字符串，让图片显示
        
        # 其他传感器返回配置的图标
        sensor_config = next((c for c in self.sensor_configs if c["key"] == sensor_key), None)
        return sensor_config.get("icon", "mdi:information") if sensor_config else "mdi:information"

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        defaults = {
            "device_name": "未知设备",
            "latest_version": "未知版本",
            "release_count": 0
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        if sensor_key == "release_count":
            return 0  # 数值型传感器返回0
            
        defaults = {
            "device_name": "加载中...",
            "latest_version": "加载中..."
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        device_name = config.get("device_name")
        if not device_name:
            raise ValueError("必须选择设备型号")
        
        if device_name not in cls.DEVICE_MAP:
            raise ValueError(f"不支持的设备型号: {device_name}")