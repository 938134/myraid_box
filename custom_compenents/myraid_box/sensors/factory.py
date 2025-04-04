from ..const import ServiceRegistry

class SensorFactory:
    @staticmethod
    def create_sensors(coordinator, entry_id: str) -> list:
        sensors = []
        for service_type in ServiceRegistry.order():
            if coordinator.entry.data.get(f"enable_{service_type}", False):
                sensors.extend(SensorFactory._create_service_sensors(
                    coordinator, service_type, entry_id
                ))
        return sensors
    
    @staticmethod
    def _create_service_sensors(coordinator, service_type: str, entry_id: str) -> list:
        service_config = ServiceRegistry.get(service_type)
        if not service_config:
            return []
        
        sensors = [SensorFactory._create_main_sensor(
            coordinator, service_type, service_config, entry_id
        )]
        
        for attr in ServiceRegistry.get_enabled_attributes(service_type):
            attr_config = ServiceRegistry.get_attributes_config(service_type)[attr]
            sensors.append(SensorFactory._create_attribute_sensor(
                coordinator, service_type, attr, attr_config, entry_id
            ))
        
        return sensors
    
    @staticmethod
    def _create_main_sensor(coordinator, service_type: str, 
                          service_config: dict, entry_id: str):
        from .main import MainSensor
        return MainSensor(
            coordinator=coordinator,
            service_type=service_type,
            name=service_config["name"],
            icon=service_config.get("icon"),
            unit=service_config.get("unit"),
            entry_id=entry_id
        )
    
    @staticmethod
    def _create_attribute_sensor(coordinator, service_type: str,
                               attr: str, attr_config: dict, entry_id: str):
        from .attribute import AttributeSensor
        return AttributeSensor(
            coordinator=coordinator,
            service_type=service_type,
            attribute=attr,
            name=f"{ServiceRegistry.get(service_type)['name']} {attr_config['name']}",
            icon=attr_config["icon"],
            unit=attr_config.get("unit"),
            entry_id=entry_id,
            device_id=f"{service_type}_{entry_id}"
        )