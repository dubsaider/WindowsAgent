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

    def _get_pnp_device_info(self, device_id: str) -> dict:
        """Получить детальную информацию об устройстве через Win32_PnPEntity"""
        try:
            pnp_devices = self.wmi_conn.Win32_PnPEntity(DeviceID=device_id)
            if pnp_devices:
                device = pnp_devices[0]
                return {
                    "manufacturer": device.Manufacturer.strip() if device.Manufacturer else None,
                    "name": device.Name.strip() if device.Name else None,
                    "description": device.Description.strip() if device.Description else None,
                    "service": device.Service.strip() if device.Service else None,
                }
        except Exception:
            pass
        return {}

    def _detect_connection_type(self, device_id: str, pnp_class: str) -> Optional[str]:
        """Определить тип подключения устройства"""
        if not device_id:
            return None
        
        device_id_upper = device_id.upper()
        pnp_class_upper = (pnp_class or "").upper()
        
        # USB устройства
        if "USB" in device_id_upper or "USB\\" in device_id_upper:
            if "BLUETOOTH" in device_id_upper:
                return "Bluetooth"
            return "USB"
        
        # Bluetooth
        if "BLUETOOTH" in device_id_upper or "BTH" in device_id_upper:
            return "Bluetooth"
        
        # PS/2
        if "PS/2" in device_id_upper or "PS2" in device_id_upper or "PNP03" in device_id_upper:
            return "PS/2"
        
        # Для мониторов
        if "MONITOR" in pnp_class_upper:
            if "DISPLAYPORT" in device_id_upper or "DP" in device_id_upper:
                return "DisplayPort"
            if "HDMI" in device_id_upper:
                return "HDMI"
            if "DVI" in device_id_upper:
                return "DVI"
            if "VGA" in device_id_upper:
                return "VGA"
        
        # Сетевые принтеры
        if "NETWORK" in device_id_upper or "TCP" in device_id_upper or "HTTP" in device_id_upper:
            return "Network"
        
        return None

    def get_peripherals(self) -> List[PeripheralDevice]:
        peripherals: List[PeripheralDevice] = []
        seen_devices = set()  # Для избежания дубликатов

        # Мониторы - используем Win32_PnPEntity для более детальной информации
        try:
            pnp_monitors = self.wmi_conn.Win32_PnPEntity(Class="Monitor")
            for pnp_mon in pnp_monitors:
                device_id = pnp_mon.DeviceID
                if device_id in seen_devices:
                    continue
                seen_devices.add(device_id)
                
                name = pnp_mon.Name.strip() if pnp_mon.Name else None
                manufacturer = pnp_mon.Manufacturer.strip() if pnp_mon.Manufacturer else None
                description = pnp_mon.Description.strip() if pnp_mon.Description else None
                connection_type = self._detect_connection_type(device_id, "Monitor")
                
                # Дополнительная информация из Win32_DesktopMonitor если доступна
                try:
                    desktop_mon = self.wmi_conn.Win32_DesktopMonitor()
                    if desktop_mon:
                        mon = desktop_mon[0]
                        if not name and mon.Name:
                            name = mon.Name.strip()
                        if not manufacturer and hasattr(mon, "MonitorManufacturer"):
                            manufacturer = mon.MonitorManufacturer.strip() if mon.MonitorManufacturer else None
                except Exception:
                    pass
                
                if name and name.lower() not in ["generic pnp monitor", "универсальный монитор pnp"]:
                    peripherals.append(
                        PeripheralDevice(
                            category="monitor",
                            name=name,
                            manufacturer=manufacturer,
                            description=description,
                            connection_type=connection_type,
                        )
                    )
        except Exception as e:
            logging.error(f"Ошибка получения информации о мониторах: {e}")

        # Клавиатуры - используем Win32_PnPEntity
        try:
            pnp_keyboards = self.wmi_conn.Win32_PnPEntity(Class="Keyboard")
            for pnp_kb in pnp_keyboards:
                device_id = pnp_kb.DeviceID
                if device_id in seen_devices:
                    continue
                seen_devices.add(device_id)
                
                name = pnp_kb.Name.strip() if pnp_kb.Name else None
                manufacturer = pnp_kb.Manufacturer.strip() if pnp_kb.Manufacturer else None
                description = pnp_kb.Description.strip() if pnp_kb.Description else None
                connection_type = self._detect_connection_type(device_id, "Keyboard")
                
                # Пропускаем виртуальные клавиатуры
                if name and "virtual" not in name.lower() and "виртуальн" not in name.lower():
                    peripherals.append(
                        PeripheralDevice(
                            category="keyboard",
                            name=name,
                            manufacturer=manufacturer,
                            description=description,
                            connection_type=connection_type,
                        )
                    )
        except Exception as e:
            logging.error(f"Ошибка получения информации о клавиатурах: {e}")

        # Мыши и указательные устройства - используем Win32_PnPEntity
        try:
            pnp_mice = self.wmi_conn.Win32_PnPEntity(Class="Mouse")
            for pnp_mouse in pnp_mice:
                device_id = pnp_mouse.DeviceID
                if device_id in seen_devices:
                    continue
                seen_devices.add(device_id)
                
                name = pnp_mouse.Name.strip() if pnp_mouse.Name else None
                manufacturer = pnp_mouse.Manufacturer.strip() if pnp_mouse.Manufacturer else None
                description = pnp_mouse.Description.strip() if pnp_mouse.Description else None
                connection_type = self._detect_connection_type(device_id, "Mouse")
                
                # Пропускаем виртуальные мыши
                if name and "virtual" not in name.lower() and "виртуальн" not in name.lower():
                    peripherals.append(
                        PeripheralDevice(
                            category="mouse",
                            name=name,
                            manufacturer=manufacturer,
                            description=description,
                            connection_type=connection_type,
                        )
                    )
        except Exception as e:
            logging.error(f"Ошибка получения информации о мышах: {e}")

        # Принтеры - улучшенная информация
        try:
            for pr in self.wmi_conn.Win32_Printer():
                name = pr.Name.strip() if pr.Name else None
                manufacturer = getattr(pr, "Manufacturer", None)
                manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer
                
                # Формируем описание из доступной информации
                description_parts = []
                if getattr(pr, "Location", None):
                    description_parts.append(f"Location: {pr.Location.strip()}")
                if getattr(pr, "Comment", None):
                    description_parts.append(pr.Comment.strip())
                if getattr(pr, "DriverName", None):
                    description_parts.append(f"Driver: {pr.DriverName.strip()}")
                if getattr(pr, "PortName", None):
                    port = pr.PortName.strip()
                    connection_type = None
                    if "USB" in port.upper():
                        connection_type = "USB"
                    elif "TCP" in port.upper() or "IP" in port.upper() or "HTTP" in port.upper():
                        connection_type = "Network"
                    elif "LPT" in port.upper():
                        connection_type = "Parallel"
                    elif "COM" in port.upper():
                        connection_type = "Serial"
                    
                    description_parts.append(f"Port: {port}")
                
                description = " | ".join(description_parts) if description_parts else None
                
                # Пропускаем виртуальные принтеры (OneNote, XPS, PDF) если они не нужны
                # Но оставим их, так как пользователь может захотеть видеть все принтеры
                
                peripherals.append(
                    PeripheralDevice(
                        category="printer",
                        name=name,
                        manufacturer=manufacturer,
                        description=description,
                        connection_type=connection_type,
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


