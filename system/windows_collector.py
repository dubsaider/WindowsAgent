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
        try:
            board = self.wmi_conn.Win32_BaseBoard()[0]
            return Motherboard(
                serial_number=board.SerialNumber.strip() if board.SerialNumber else None,
                model=board.Product.strip() if board.Product else None,
                manufacturer=board.Manufacturer.strip() if board.Manufacturer else None,
                product=board.Product.strip() if board.Product else None,
            )
        except Exception as e:
            logging.error(f"Ошибка получения информации о материнской плате: {e}")
            return None

    def get_cpu(self) -> Optional[CPU]:
        try:
            cpu = self.wmi_conn.Win32_Processor()[0]
            return CPU(
                serial_number=None,
                model=cpu.Name.strip() if cpu.Name else None,
                manufacturer=cpu.Manufacturer.strip() if cpu.Manufacturer else None,
                name=cpu.Name.strip() if cpu.Name else None,
                cores=cpu.NumberOfCores if cpu.NumberOfCores else None,
                threads=cpu.NumberOfLogicalProcessors if cpu.NumberOfLogicalProcessors else None,
            )
        except Exception as e:
            logging.error(f"Ошибка получения информации о процессоре: {e}")
            return None

    def get_ram_modules(self) -> List[RAMModule]:
        modules: List[RAMModule] = []
        try:
            ram_list = self.wmi_conn.Win32_PhysicalMemory()
            for idx, ram in enumerate(ram_list):
                size_gb = int(ram.Capacity) // (1024 ** 3) if ram.Capacity else None
                module = RAMModule(
                    serial_number=ram.SerialNumber.strip() if ram.SerialNumber else None,
                    model=ram.PartNumber.strip() if ram.PartNumber else None,
                    size_gb=size_gb,
                    slot=ram.DeviceLocator.strip() if ram.DeviceLocator else f"Slot{idx}",
                    speed=f"{ram.Speed}MHz" if ram.Speed else None,
                    manufacturer=ram.Manufacturer.strip() if ram.Manufacturer else None,
                )
                modules.append(module)
        except Exception as e:
            logging.error(f"Ошибка получения информации о RAM: {e}")
        return modules

    def get_storage_devices(self) -> List[Storage]:
        devices: List[Storage] = []
        try:
            disks = self.wmi_conn.Win32_DiskDrive()
            for disk in disks:
                size_gb = int(disk.Size) // (1024 ** 3) if disk.Size else None

                interface = disk.InterfaceType.strip() if disk.InterfaceType else None
                storage_type = "HDD"
                if "SSD" in (disk.MediaType or "").upper() or "SSD" in (disk.Model or "").upper():
                    storage_type = "SSD"
                if "NVME" in (disk.InterfaceType or "").upper() or "NVME" in (disk.Model or "").upper():
                    storage_type = "NVMe"
                    interface = "NVMe"

                device = Storage(
                    serial_number=disk.SerialNumber.strip() if disk.SerialNumber else None,
                    model=disk.Model.strip() if disk.Model else None,
                    size_gb=size_gb,
                    interface=interface,
                    type=storage_type,
                )
                devices.append(device)
        except Exception as e:
            logging.error(f"Ошибка получения информации о накопителях: {e}")
        return devices

    def get_gpu(self) -> Optional[GPU]:
        try:
            gpus = self.wmi_conn.Win32_VideoController()
            for gpu in gpus:
                if "Intel" in (gpu.Name or ""):
                    continue
                memory_gb = int(gpu.AdapterRAM) // (1024 ** 3) if gpu.AdapterRAM else None
                return GPU(
                    serial_number=None,
                    model=gpu.Name.strip() if gpu.Name else None,
                    manufacturer=gpu.AdapterCompatibility.strip() if gpu.AdapterCompatibility else None,
                    name=gpu.Name.strip() if gpu.Name else None,
                    memory_gb=memory_gb,
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации о видеокарте: {e}")
        return None

    def get_network_adapters(self) -> List[NetworkAdapter]:
        adapters: List[NetworkAdapter] = []
        try:
            nics = self.wmi_conn.Win32_NetworkAdapterConfiguration(IPEnabled=True)
            for nic in nics:
                if nic.MACAddress:
                    ip_addresses = list(nic.IPAddress) if getattr(nic, "IPAddress", None) else None
                    subnets = list(nic.IPSubnet) if getattr(nic, "IPSubnet", None) else None
                    gateways = list(nic.DefaultIPGateway) if getattr(nic, "DefaultIPGateway", None) else None
                    dns_servers = list(nic.DNSServerSearchOrder) if getattr(
                        nic, "DNSServerSearchOrder", None
                    ) else None

                    adapter = NetworkAdapter(
                        mac_address=nic.MACAddress.strip(),
                        name=nic.Description.strip() if nic.Description else None,
                        manufacturer=None,
                        ip_addresses=ip_addresses,
                        subnets=subnets,
                        gateways=gateways,
                        dns_servers=dns_servers,
                    )
                    adapters.append(adapter)
        except Exception as e:
            logging.error(f"Ошибка получения информации о сетевых адаптерах: {e}")
        return adapters

    def get_psu(self) -> Optional[PSU]:
        """Информация о БП обычно недоступна через стандартный WMI."""
        return None

    def get_peripherals(self) -> List[PeripheralDevice]:
        peripherals: List[PeripheralDevice] = []

        try:
            for mon in self.wmi_conn.Win32_DesktopMonitor():
                name = (mon.Name or mon.Caption or "").strip() or None
                manufacturer = getattr(mon, "MonitorManufacturer", None)
                manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer
                peripherals.append(
                    PeripheralDevice(
                        category="monitor",
                        name=name,
                        manufacturer=manufacturer,
                        description=mon.Caption.strip() if mon.Caption else None,
                        connection_type=None,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации о мониторах: {e}")

        try:
            for kb in self.wmi_conn.Win32_Keyboard():
                peripherals.append(
                    PeripheralDevice(
                        category="keyboard",
                        name=kb.Description.strip() if kb.Description else None,
                        manufacturer=None,
                        description=kb.Name.strip() if kb.Name else None,
                        connection_type=None,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации о клавиатурах: {e}")

        try:
            for pd in self.wmi_conn.Win32_PointingDevice():
                peripherals.append(
                    PeripheralDevice(
                        category="mouse",
                        name=pd.Description.strip() if pd.Description else None,
                        manufacturer=None,
                        description=pd.Name.strip() if pd.Name else None,
                        connection_type=None,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации об указательных устройствах: {e}")

        try:
            for pr in self.wmi_conn.Win32_Printer():
                manufacturer = getattr(pr, "Manufacturer", None)
                manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer
                description = None
                if getattr(pr, "Location", None):
                    description = pr.Location.strip()
                elif getattr(pr, "Comment", None):
                    description = pr.Comment.strip()

                peripherals.append(
                    PeripheralDevice(
                        category="printer",
                        name=pr.Name.strip() if pr.Name else None,
                        manufacturer=manufacturer,
                        description=description,
                        connection_type=None,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации о принтерах: {e}")

        return peripherals

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
        )


