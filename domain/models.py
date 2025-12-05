"""
Доменные модели данных для системы PC-Guardian.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class HardwareComponent:
    """Базовый класс для компонента оборудования"""

    serial_number: Optional[str] = None
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Motherboard(HardwareComponent):
    """Материнская плата"""

    manufacturer: Optional[str] = None
    product: Optional[str] = None


@dataclass
class CPU(HardwareComponent):
    """Процессор"""

    manufacturer: Optional[str] = None
    name: Optional[str] = None
    cores: Optional[int] = None
    threads: Optional[int] = None


@dataclass
class RAMModule(HardwareComponent):
    """Модуль оперативной памяти"""

    size_gb: Optional[int] = None
    slot: Optional[str] = None
    speed: Optional[str] = None
    manufacturer: Optional[str] = None


@dataclass
class Storage(HardwareComponent):
    """Накопитель (HDD/SSD/NVMe)"""

    size_gb: Optional[int] = None
    interface: Optional[str] = None  # SATA, NVMe, etc.
    type: Optional[str] = None  # HDD, SSD, NVMe


@dataclass
class GPU(HardwareComponent):
    """Видеокарта"""

    manufacturer: Optional[str] = None
    name: Optional[str] = None
    memory_gb: Optional[int] = None


@dataclass
class NetworkAdapter:
    """Сетевой адаптер"""

    mac_address: str
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    # Сетевые параметры
    ip_addresses: Optional[List[str]] = None
    subnets: Optional[List[str]] = None
    gateways: Optional[List[str]] = None
    dns_servers: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PSU:
    """Блок питания"""

    model: Optional[str] = None
    manufacturer: Optional[str] = None
    wattage: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemInfo:
    """Инфраструктурная информация о системе"""

    domain: Optional[str] = None  # Доменное имя (например, example.com)
    domain_role: Optional[str] = None  # Роль в домене (Workstation, Member Server, Domain Controller и т.д.)
    workgroup: Optional[str] = None  # Рабочая группа (если не в домене)
    part_of_domain: Optional[bool] = None  # Является ли компьютер членом домена
    manufacturer: Optional[str] = None  # Производитель системы
    model: Optional[str] = None  # Модель системы
    system_type: Optional[str] = None  # Тип системы (x64-based PC и т.д.)
    total_physical_memory_gb: Optional[float] = None  # Общий объем физической памяти в GB
    os_name: Optional[str] = None  # Название ОС
    os_version: Optional[str] = None  # Версия ОС
    os_build: Optional[str] = None  # Сборка ОС
    os_architecture: Optional[str] = None  # Архитектура ОС (64-bit, 32-bit)
    os_install_date: Optional[str] = None  # Дата установки ОС
    logged_in_user: Optional[str] = None  # Текущий пользователь
    timezone: Optional[str] = None  # Часовой пояс

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PeripheralDevice:
    """Устройство периферии (монитор, клавиатура, мышь, принтер, камера, аудио и т.п.)"""

    category: str  # monitor, keyboard, mouse, printer, camera, microphone, speaker, audio, other
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    connection_type: Optional[str] = None  # USB, Bluetooth, PS/2, HDMI, DisplayPort и т.п.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PCConfiguration:
    """Полная конфигурация ПК"""

    pc_id: str  # Уникальный идентификатор ПК
    hostname: str
    agent_version: Optional[str] = None  # Версия агента
    motherboard: Optional[Motherboard] = None
    cpu: Optional[CPU] = None
    ram_modules: List[RAMModule] = None
    storage_devices: List[Storage] = None
    gpu: Optional[GPU] = None
    network_adapters: List[NetworkAdapter] = None
    psu: Optional[PSU] = None
    peripherals: List[PeripheralDevice] = None
    system_info: Optional["SystemInfo"] = None  # Инфраструктурная информация
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.ram_modules is None:
            self.ram_modules = []
        if self.storage_devices is None:
            self.storage_devices = []
        if self.network_adapters is None:
            self.network_adapters = []
        if self.peripherals is None:
            self.peripherals = []
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для отправки в Kafka"""
        result = {
            "pc_id": self.pc_id,
            "hostname": self.hostname,
            "agent_version": self.agent_version,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

        if self.motherboard:
            result["motherboard"] = self.motherboard.to_dict()
        if self.cpu:
            result["cpu"] = self.cpu.to_dict()
        if self.ram_modules:
            result["ram_modules"] = [m.to_dict() for m in self.ram_modules]
        if self.storage_devices:
            result["storage_devices"] = [s.to_dict() for s in self.storage_devices]
        if self.gpu:
            result["gpu"] = self.gpu.to_dict()
        if self.network_adapters:
            result["network_adapters"] = [n.to_dict() for n in self.network_adapters]
        if self.psu:
            result["psu"] = self.psu.to_dict()
        if self.peripherals:
            result["peripherals"] = [p.to_dict() for p in self.peripherals]
        if self.system_info:
            result["system_info"] = self.system_info.to_dict()

        return result

    def to_json(self) -> str:
        """Преобразование в JSON строку"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PCConfiguration":
        """Создание из словаря"""
        config = cls(
            pc_id=data.get("pc_id"),
            hostname=data.get("hostname"),
            agent_version=data.get("agent_version"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if data.get("timestamp")
            else None,
        )

        if data.get("motherboard"):
            config.motherboard = Motherboard(**data["motherboard"])
        if data.get("cpu"):
            config.cpu = CPU(**data["cpu"])
        if data.get("ram_modules"):
            config.ram_modules = [RAMModule(**m) for m in data["ram_modules"]]
        if data.get("storage_devices"):
            config.storage_devices = [Storage(**s) for s in data["storage_devices"]]
        if data.get("gpu"):
            config.gpu = GPU(**data["gpu"])
        if data.get("network_adapters"):
            config.network_adapters = [
                NetworkAdapter(**n) for n in data["network_adapters"]
            ]
        if data.get("psu"):
            config.psu = PSU(**data["psu"])
        if data.get("peripherals"):
            config.peripherals = [PeripheralDevice(**p) for p in data["peripherals"]]
        if data.get("system_info"):
            config.system_info = SystemInfo(**data["system_info"])

        return config


@dataclass
class ChangeEvent:
    """Событие изменения конфигурации"""

    pc_id: str
    component_type: str  # motherboard, cpu, ram, storage, gpu, network, psu
    event_type: str  # removed, added, replaced
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    details: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pc_id": self.pc_id,
            "component_type": self.component_type,
            "event_type": self.event_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
        }


