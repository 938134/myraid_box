from typing import Dict, Any, List
from datetime import datetime
import logging
import aiohttp
import json
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class IStoreOSService(BaseService):
    """多传感器版 iStoreOS 固件版本服务"""

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
            self._create_sensor_config("device_name", "设备型号", "mdi:devices", None, None, 1),
            self._create_sensor_config("latest_version", "最新版本", "mdi:tag", None, None, 2),
            self._create_sensor_config("release_count", "发布数量", "mdi:counter", "个", None, 3),
        ]

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """重写数据获取方法以支持POST请求"""
        await self._ensure_session()
        try:
            device_name = params.get("device_name", "seed-ac2")
            
            # 构建POST请求数据
            post_data = {
                "deviceName": device_name,
                "firmwareName": "iStoreOS"
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}",
                "Accept": "application/json"
            }
            
            async with self._session.post(
                self.DEFAULT_API_URL, 
                json=post_data, 
                headers=headers
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                return {
                    "data": data,
                    "status": "success",
                    "error": None,
                    "update_time": datetime.now().isoformat()
                }
                    
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
            device_info = result.get("device", {})
            releases = result.get("releases", [])
            
            # 获取最新版本
            latest_release = releases[0] if releases else {}
            latest_version = latest_release.get("release", "未知")
            
            # 获取设备显示名称
            device_display_name = self.DEVICE_MAP.get(
                self._get_device_from_config(), 
                self._get_device_from_config()
            )

            return {
                "status": "success",
                "device_name": device_display_name,
                "latest_version": latest_version,
                "device_cover": device_info.get("cover", ""),
                "release_count": len(releases),
                "firmware_name": "iStoreOS",  # 保留在数据中供属性使用
                "update_time": update_time
            }
            
        except Exception as e:
            _LOGGER.error("[iStoreOS] 解析响应数据时发生异常: %s", str(e), exc_info=True)
            return self._create_error_response(f"解析错误: {str(e)}", datetime.now().isoformat())

    def _get_device_from_config(self) -> str:
        """从配置中获取设备名称"""
        # 这个方法会在format_sensor_value中被调用，需要从数据中获取设备名称
        return "seed-ac2"  # 默认值

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
        
        # 为设备型号传感器添加详细信息
        if sensor_key == "device_name":
            attributes["设备图片"] = data.get("device_cover", "无图片")
            attributes["固件名称"] = data.get("firmware_name", "iStoreOS")
            attributes["发布数量"] = data.get("release_count", 0)
        
        # 为版本传感器添加详细信息
        elif sensor_key == "latest_version":
            attributes["设备型号"] = data.get("device_name", "未知")
            attributes["固件名称"] = data.get("firmware_name", "iStoreOS")
            attributes["发布数量"] = data.get("release_count", 0)
        
        # 为发布数量传感器添加详细信息
        elif sensor_key == "release_count":
            attributes["设备型号"] = data.get("device_name", "未知")
            attributes["最新版本"] = data.get("latest_version", "未知")
            attributes["固件名称"] = data.get("firmware_name", "iStoreOS")
        
        return attributes

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        device_name = config.get("device_name")
        if not device_name:
            raise ValueError("必须选择设备型号")
        
        if device_name not in cls.DEVICE_MAP:
            raise ValueError(f"不支持的设备型号: {device_name}")