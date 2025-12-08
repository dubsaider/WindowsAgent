"""
Слой взаимодействия с операционной системой (Windows/WMI).

Содержит классы и функции, которые знают, как получить информацию
из ОС и WMI, но ничего не знают про Kafka и форматы сообщений.
"""

import logging
import socket
from typing import Optional, List

import wmi

from domain.models import (
    PCConfiguration,
    Motherboard,
    CPU,
    RAMModule,
    Storage,
    GPU,
    NetworkAdapter,
    PSU,
    PeripheralDevice,
    HIDDevice,
    SystemInfo,
)
from system.pnp_utils import detect_connection_type
from system.peripherals import collect_peripherals
from system.hid_aggregator import collect_hid_devices
from system.system_info import collect_system_info
from system.hardware import (
    get_motherboard,
    get_cpu,
    get_ram_modules,
    get_storage_devices,
    get_gpu,
    get_network_adapters,
    get_psu,
)

try:
    from __version__ import __version__ as AGENT_VERSION
except ImportError:
    AGENT_VERSION = "unknown"


class WindowsHardwareCollector:
    """Класс для сбора информации о комплектующих и периферии в Windows"""

    def __init__(self):
        self.wmi_conn = wmi.WMI()
        self.hostname = socket.gethostname()

    def get_pc_id(self) -> str:
        """Получить уникальный идентификатор ПК"""
        try:
            motherboard = self.wmi_conn.Win32_BaseBoard()[0]
            serial = motherboard.SerialNumber.strip()
            if serial and serial != "To be filled by O.E.M.":
                return f"{serial}_{self.hostname}"
            system = self.wmi_conn.Win32_ComputerSystemProduct()[0]
            uuid = system.UUID
            return f"{uuid}_{self.hostname}"
        except Exception as e:
            logging.error(f"Ошибка получения PC ID: {e}")
            return f"UNKNOWN_{self.hostname}"

    def get_motherboard(self) -> Optional[Motherboard]:
        return get_motherboard(self.wmi_conn)

    def get_cpu(self) -> Optional[CPU]:
        return get_cpu(self.wmi_conn)

    def get_ram_modules(self) -> List[RAMModule]:
        return get_ram_modules(self.wmi_conn)

    def get_storage_devices(self) -> List[Storage]:
        return get_storage_devices(self.wmi_conn)

    def get_gpu(self) -> Optional[GPU]:
        return get_gpu(self.wmi_conn)

    def get_network_adapters(self) -> List[NetworkAdapter]:
        return get_network_adapters(self.wmi_conn)

    def get_psu(self) -> Optional[PSU]:
        return get_psu(self.wmi_conn)

    def get_system_info(self) -> Optional[SystemInfo]:
        return collect_system_info(self.wmi_conn)

    def get_peripherals(self) -> List[PeripheralDevice]:
        return collect_peripherals(self.wmi_conn)

    def get_hid_devices(self) -> List[HIDDevice]:
        return collect_hid_devices(self.wmi_conn)

    def collect_configuration(self) -> PCConfiguration:
        """Собрать полную конфигурацию ПК (со стороны ОС/WMI)."""
        pc_id = self.get_pc_id()
        return PCConfiguration(
            pc_id=pc_id,
            hostname=self.hostname,
            agent_version=AGENT_VERSION,
            motherboard=self.get_motherboard(),
            cpu=self.get_cpu(),
            ram_modules=self.get_ram_modules(),
            storage_devices=self.get_storage_devices(),
            gpu=self.get_gpu(),
            network_adapters=self.get_network_adapters(),
            psu=self.get_psu(),
            peripherals=self.get_peripherals(),
            system_info=self.get_system_info(),
            hid_devices=self.get_hid_devices(),
        )


