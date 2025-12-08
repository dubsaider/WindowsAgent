"""
Слой взаимодействия с операционной системой (Windows/WMI).

Содержит классы и функции, которые знают, как получить информацию
из ОС и WMI, но ничего не знают про Kafka и форматы сообщений.
"""

import logging
import re
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
                # Исправляем проблему с памятью (-1 означает неизвестно)
                memory_gb = None
                if gpu.AdapterRAM and int(gpu.AdapterRAM) > 0:
                    memory_gb = int(gpu.AdapterRAM) // (1024 ** 3)
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

    def get_system_info(self) -> Optional[SystemInfo]:
        """Получить инфраструктурную информацию о системе"""
        try:
            # Информация о компьютере и домене
            computer_system = self.wmi_conn.Win32_ComputerSystem()[0]
            
            domain = computer_system.Domain.strip() if computer_system.Domain else None
            workgroup = computer_system.Workgroup.strip() if computer_system.Workgroup else None
            part_of_domain = computer_system.PartOfDomain if hasattr(computer_system, 'PartOfDomain') else None
            
            # Роль в домене
            domain_role = None
            if hasattr(computer_system, 'DomainRole'):
                role = computer_system.DomainRole
                role_map = {
                    0: "Standalone Workstation",
                    1: "Member Workstation",
                    2: "Standalone Server",
                    3: "Member Server",
                    4: "Backup Domain Controller",
                    5: "Primary Domain Controller"
                }
                domain_role = role_map.get(role, f"Unknown ({role})")
            
            manufacturer = computer_system.Manufacturer.strip() if computer_system.Manufacturer else None
            model = computer_system.Model.strip() if computer_system.Model else None
            system_type = computer_system.SystemType.strip() if computer_system.SystemType else None
            
            # Общая память
            total_memory = computer_system.TotalPhysicalMemory
            total_memory_gb = None
            if total_memory:
                total_memory_gb = round(int(total_memory) / (1024 ** 3), 2)
            
            # Информация об ОС
            os_info = self.wmi_conn.Win32_OperatingSystem()[0]
            os_name = os_info.Caption.strip() if os_info.Caption else None
            os_version = os_info.Version.strip() if os_info.Version else None
            os_build = os_info.BuildNumber.strip() if os_info.BuildNumber else None
            os_architecture = os_info.OSArchitecture.strip() if hasattr(os_info, 'OSArchitecture') and os_info.OSArchitecture else None
            
            # Дата установки ОС
            os_install_date = None
            if hasattr(os_info, 'InstallDate') and os_info.InstallDate:
                try:
                    # WMI возвращает дату в формате YYYYMMDDHHmmss.ffffff+UUU
                    install_date_str = str(os_info.InstallDate)
                    if len(install_date_str) >= 8:
                        year = install_date_str[0:4]
                        month = install_date_str[4:6]
                        day = install_date_str[6:8]
                        os_install_date = f"{year}-{month}-{day}"
                except Exception:
                    pass
            
            # Текущий пользователь
            logged_in_user = None
            try:
                if hasattr(os_info, 'RegisteredUser') and os_info.RegisteredUser:
                    logged_in_user = os_info.RegisteredUser.strip()
            except Exception:
                pass
            
            # Часовой пояс
            timezone = None
            try:
                if hasattr(os_info, 'CurrentTimeZone'):
                    tz_offset = os_info.CurrentTimeZone
                    if tz_offset is not None:
                        hours = abs(tz_offset) // 60
                        minutes = abs(tz_offset) % 60
                        sign = "+" if tz_offset >= 0 else "-"
                        timezone = f"UTC{sign}{hours:02d}:{minutes:02d}"
            except Exception:
                pass
            
            return SystemInfo(
                domain=domain,
                domain_role=domain_role,
                workgroup=workgroup,
                part_of_domain=part_of_domain,
                manufacturer=manufacturer,
                model=model,
                system_type=system_type,
                total_physical_memory_gb=total_memory_gb,
                os_name=os_name,
                os_version=os_version,
                os_build=os_build,
                os_architecture=os_architecture,
                os_install_date=os_install_date,
                logged_in_user=logged_in_user,
                timezone=timezone,
            )
        except Exception as e:
            logging.error(f"Ошибка получения системной информации: {e}")
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

    def _is_virtual_device(self, name: str, device_id: str = None) -> bool:
        """Проверка, является ли устройство виртуальным"""
        if not name:
            return False
        name_lower = name.lower()
        # Более точные проверки на виртуальные устройства
        virtual_patterns = [
            "virtual", "виртуальн",
            "vmware", "virtualbox", "hyper-v",
            "remote desktop", "rdp",
            "microsoft virtual", "microsoft remote",
            "microsoft print to pdf",  # Виртуальный принтер
            "microsoft xps document writer",  # Виртуальный принтер
            "onenote",  # Виртуальный принтер
        ]
        return any(pattern in name_lower for pattern in virtual_patterns)

    def _is_system_device(self, name: str, pnp_class: str = None) -> bool:
        """Проверка, является ли устройство системным (не периферией)"""
        if not name:
            return False
        name_lower = name.lower()
        pnp_class_lower = (pnp_class or "").lower()
        
        # Системные устройства, которые не являются периферией
        system_patterns = [
            "usb-концентратор", "usb hub", "usb host controller", "хост-контроллер",
            "usb root hub", "корневой usb-концентратор", "универсальный usb-концентратор",
            "hid-совместимый системный контроллер", "hid-совместимое устройство управления",
            "hid-совместимое устройство, определенное поставщиком",
            "составное usb устройство", "composite usb device",
            "стандартный usb хост-контроллер", "standard usb host controller",
            "xhci", "ehci", "ohci", "uhci",
        ]
        
        system_classes = ["system", "systemdevice", "usbcontroller", "usbhub"]
        
        return (any(pattern in name_lower for pattern in system_patterns) or
                any(cls in pnp_class_lower for cls in system_classes))

    def _normalize_device_name(self, name: str) -> str:
        """Нормализация названия устройства для сравнения"""
        if not name:
            return ""
        # Убираем стандартные префиксы и суффиксы
        normalized = name.lower()
        # Убираем стандартные префиксы
        prefixes = ["generic", "универсальный", "стандартный", "standard"]
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        # Убираем стандартные суффиксы в скобках
        normalized = re.sub(r'\s*\(\([^)]+\)\)', '', normalized)  # ((Стандартные мониторы))
        normalized = re.sub(r'\s*\([^)]*стандарт[^)]*\)', '', normalized, flags=re.IGNORECASE)
        return normalized.strip()

    def _add_peripheral(self, peripherals: List[PeripheralDevice], seen_devices: set,
                       category: str, name: Optional[str], manufacturer: Optional[str],
                       description: Optional[str], connection_type: Optional[str],
                       device_id: str = None, pnp_class: str = None) -> bool:
        """Добавить периферийное устройство, избегая дубликатов"""
        if not name:
            return False
        
        # Пропускаем виртуальные устройства
        if self._is_virtual_device(name, device_id):
            return False
        
        # Пропускаем системные устройства
        if self._is_system_device(name, pnp_class):
            return False
        
        # Используем device_id как основной ключ для определения дубликатов
        # Если device_id есть - это уникальное устройство, даже если названия одинаковые
        if device_id:
            if device_id in seen_devices:
                return False
            seen_devices.add(device_id)
        else:
            # Если device_id нет, используем комбинацию категории, имени и производителя
            key = f"{category}_{name}_{manufacturer or ''}"
            if key in seen_devices:
                return False
            seen_devices.add(key)
        
        peripherals.append(
            PeripheralDevice(
                category=category,
                name=name,
                manufacturer=manufacturer,
                description=description,
                connection_type=connection_type,
            )
        )
        return True

    def get_peripherals(self) -> List[PeripheralDevice]:
        peripherals: List[PeripheralDevice] = []
        seen_devices = set()  # Для избежания дубликатов

        # Получаем все PnP устройства и фильтруем по PNPClass
        pnp_devices_by_class = {}
        try:
            all_pnp_devices = self.wmi_conn.Win32_PnPEntity()
            for device in all_pnp_devices:
                pnp_class = getattr(device, "PNPClass", None)
                if pnp_class:
                    if pnp_class not in pnp_devices_by_class:
                        pnp_devices_by_class[pnp_class] = []
                    pnp_devices_by_class[pnp_class].append(device)
        except Exception as e:
            logging.warning(f"Не удалось получить PnP устройства: {e}")

        # Мониторы - используем оба метода для максимального покрытия
        try:
            # Сначала собираем из PnP устройств
            monitors_pnp = pnp_devices_by_class.get("Monitor", [])
            for pnp_mon in monitors_pnp:
                device_id = pnp_mon.DeviceID
                name = pnp_mon.Name.strip() if pnp_mon.Name else None
                manufacturer = pnp_mon.Manufacturer.strip() if pnp_mon.Manufacturer else None
                description = pnp_mon.Description.strip() if pnp_mon.Description else None
                connection_type = self._detect_connection_type(device_id, "Monitor")
                
                self._add_peripheral(peripherals, seen_devices, "monitor", name, 
                                   manufacturer, description, connection_type, device_id, "Monitor")
            
            # Затем дополняем из Win32_DesktopMonitor (может быть больше информации)
            try:
                desktop_monitors = self.wmi_conn.Win32_DesktopMonitor()
                for mon in desktop_monitors:
                    device_id = getattr(mon, "DeviceID", None) or f"monitor_desktop_{len(peripherals)}"
                    name = (mon.Name or mon.Caption or "").strip() or None
                    manufacturer = getattr(mon, "MonitorManufacturer", None)
                    manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer
                    description = mon.Caption.strip() if mon.Caption else None
                    connection_type = None
                    
                    self._add_peripheral(peripherals, seen_devices, "monitor", name,
                                       manufacturer, description, connection_type, device_id, "Monitor")
            except Exception:
                pass  # Если не удалось получить, продолжаем
                
        except Exception as e:
            logging.error(f"Ошибка получения информации о мониторах: {e}")

        # Клавиатуры - используем оба метода
        try:
            # Сначала из PnP устройств
            keyboards_pnp = pnp_devices_by_class.get("Keyboard", [])
            for pnp_kb in keyboards_pnp:
                device_id = pnp_kb.DeviceID
                name = pnp_kb.Name.strip() if pnp_kb.Name else None
                manufacturer = pnp_kb.Manufacturer.strip() if pnp_kb.Manufacturer else None
                description = pnp_kb.Description.strip() if pnp_kb.Description else None
                connection_type = self._detect_connection_type(device_id, "Keyboard")
                
                self._add_peripheral(peripherals, seen_devices, "keyboard", name,
                                   manufacturer, description, connection_type, device_id, "Keyboard")
            
            # Затем из Win32_Keyboard
            try:
                keyboards_wmi = self.wmi_conn.Win32_Keyboard()
                for kb in keyboards_wmi:
                    device_id = getattr(kb, "DeviceID", None) or f"keyboard_wmi_{len(peripherals)}"
                    name = kb.Description.strip() if kb.Description else None
                    description = kb.Name.strip() if kb.Name else None
                    connection_type = None
                    
                    self._add_peripheral(peripherals, seen_devices, "keyboard", name,
                                       None, description, connection_type, device_id, "Keyboard")
            except Exception:
                pass
                
        except Exception as e:
            logging.error(f"Ошибка получения информации о клавиатурах: {e}")

        # Мыши и указательные устройства - используем оба метода
        try:
            # Сначала из PnP устройств
            mice_pnp = pnp_devices_by_class.get("Mouse", [])
            for pnp_mouse in mice_pnp:
                device_id = pnp_mouse.DeviceID
                name = pnp_mouse.Name.strip() if pnp_mouse.Name else None
                manufacturer = pnp_mouse.Manufacturer.strip() if pnp_mouse.Manufacturer else None
                description = pnp_mouse.Description.strip() if pnp_mouse.Description else None
                connection_type = self._detect_connection_type(device_id, "Mouse")
                
                self._add_peripheral(peripherals, seen_devices, "mouse", name,
                                   manufacturer, description, connection_type, device_id, "Mouse")
            
            # Затем из Win32_PointingDevice
            try:
                mice_wmi = self.wmi_conn.Win32_PointingDevice()
                for pd in mice_wmi:
                    device_id = getattr(pd, "DeviceID", None) or f"mouse_wmi_{len(peripherals)}"
                    name = pd.Description.strip() if pd.Description else None
                    description = pd.Name.strip() if pd.Name else None
                    connection_type = None
                    
                    self._add_peripheral(peripherals, seen_devices, "mouse", name,
                                       None, description, connection_type, device_id, "Mouse")
            except Exception:
                pass
                
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
                device_id = f"printer_{name or len(peripherals)}"
                
                self._add_peripheral(peripherals, seen_devices, "printer", name,
                                   manufacturer, description, connection_type, device_id, "Printer")
        except Exception as e:
            logging.error(f"Ошибка получения информации о принтерах: {e}")

        # Веб-камеры и камеры (не путать со сканерами)
        try:
            cameras = pnp_devices_by_class.get("Camera", [])
            for cam in cameras:
                device_id = cam.DeviceID
                name = cam.Name.strip() if cam.Name else None
                # Пропускаем сканеры (они часто попадают в Image класс)
                if name and ("scanner" in name.lower() or "сканер" in name.lower() or "wsd устройство сканирования" in name.lower()):
                    continue
                manufacturer = cam.Manufacturer.strip() if cam.Manufacturer else None
                description = cam.Description.strip() if cam.Description else None
                connection_type = self._detect_connection_type(device_id, "Camera")
                
                self._add_peripheral(peripherals, seen_devices, "camera", name,
                                   manufacturer, description, connection_type, device_id, "Camera")
        except Exception as e:
            logging.error(f"Ошибка получения информации о камерах: {e}")

        # Аудио устройства (микрофоны, динамики) - исключаем аудио выходы мониторов
        try:
            audio_devices = pnp_devices_by_class.get("AudioEndpoint", []) + \
                          pnp_devices_by_class.get("Media", []) + \
                          pnp_devices_by_class.get("Sound", [])
            for audio in audio_devices:
                device_id = audio.DeviceID
                name = audio.Name.strip() if audio.Name else None
                # Пропускаем аудио выходы мониторов (они не являются отдельной периферией)
                if name and ("high definition audio" in name.lower() and 
                            any(mon_name in name.lower() for mon_name in ["nvidia", "amd", "intel"])):
                    continue
                manufacturer = audio.Manufacturer.strip() if audio.Manufacturer else None
                description = audio.Description.strip() if audio.Description else None
                connection_type = self._detect_connection_type(device_id, "Audio")
                
                # Определяем тип аудио устройства
                category = "audio"
                if name:
                    name_lower = name.lower()
                    if "microphone" in name_lower or "микрофон" in name_lower:
                        category = "microphone"
                    elif "speaker" in name_lower or "headphone" in name_lower or "динамик" in name_lower or "наушник" in name_lower:
                        category = "speaker"
                
                self._add_peripheral(peripherals, seen_devices, category, name,
                                   manufacturer, description, connection_type, device_id, "Audio")
        except Exception as e:
            logging.error(f"Ошибка получения информации об аудио устройствах: {e}")

        # Другие USB устройства (HID, USB устройства и т.д.) - только реальная периферия
        try:
            other_usb = pnp_devices_by_class.get("USB", []) + \
                       pnp_devices_by_class.get("HIDClass", [])
            for device in other_usb:
                device_id = device.DeviceID
                name = device.Name.strip() if device.Name else None
                pnp_class = getattr(device, "PNPClass", None)
                
                # Пропускаем системные устройства
                if self._is_system_device(name, pnp_class):
                    continue
                
                # Пропускаем уже обработанные категории и виртуальные устройства
                if not name or self._is_virtual_device(name, device_id):
                    continue
                
                # Пропускаем устройства, которые уже были обработаны как клавиатуры, мыши и т.д.
                name_lower = name.lower()
                if any(keyword in name_lower for keyword in ["keyboard", "клавиатур", "mouse", "мыш", 
                                                              "monitor", "монитор", "printer", "принтер",
                                                              "camera", "камер", "audio", "аудио",
                                                              "scanner", "сканер"]):
                    continue
                
                manufacturer = device.Manufacturer.strip() if device.Manufacturer else None
                description = device.Description.strip() if device.Description else None
                connection_type = self._detect_connection_type(device_id, "USB")
                
                self._add_peripheral(peripherals, seen_devices, "other", name,
                                   manufacturer, description, connection_type, device_id, pnp_class)
        except Exception as e:
            logging.error(f"Ошибка получения информации о других USB устройствах: {e}")

        return peripherals

    def _parse_usb_id(self, device_id: str) -> tuple:
        """Извлечь VID/PID/serial из PNPDeviceID"""
        if not device_id:
            return None, None, None
        vid = pid = serial = None
        try:
            vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", device_id)
            pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", device_id)
            if vid_match:
                vid = vid_match.group(1).upper()
            if pid_match:
                pid = pid_match.group(1).upper()
            # serial обычно после последнего '\'
            if "\\" in device_id:
                serial_candidate = device_id.split("\\")[-1]
                if serial_candidate and "{" not in serial_candidate:
                    serial = serial_candidate
        except Exception:
            pass
        return vid, pid, serial

    def get_hid_devices(self) -> List[HIDDevice]:
        """
        Агрегировать HID по физическому устройству:
        ключ = vid:pid + serial (если есть) + usb_path/bus-port
        """
        hid_devices: List[HIDDevice] = []
        seen_keys = {}

        # Собираем все PnP устройства, относящиеся к HID / клавиатурам / мышам
        pnp_hid = []
        try:
            all_pnp = self.wmi_conn.Win32_PnPEntity()
            for dev in all_pnp:
                pnp_class = getattr(dev, "PNPClass", "") or ""
                if pnp_class in ("HIDClass", "Keyboard", "Mouse"):
                    pnp_hid.append(dev)
        except Exception as e:
            logging.error(f"Ошибка получения PnP HID: {e}")
            return hid_devices

        for dev in pnp_hid:
            device_id = getattr(dev, "PNPDeviceID", None) or getattr(dev, "DeviceID", None)
            name = dev.Name.strip() if getattr(dev, "Name", None) else None
            manufacturer = dev.Manufacturer.strip() if getattr(dev, "Manufacturer", None) else None
            description = dev.Description.strip() if getattr(dev, "Description", None) else None
            pnp_class = getattr(dev, "PNPClass", "") or ""

            # Определяем интерфейсы
            interfaces = []
            lower_name = (name or "").lower()
            if pnp_class.lower() == "keyboard" or "keyboard" in lower_name or "клавиатур" in lower_name:
                interfaces.append("keyboard")
            if pnp_class.lower() == "mouse" or "mouse" in lower_name or "мыш" in lower_name:
                interfaces.append("mouse")
            if not interfaces and pnp_class.lower() == "hidclass":
                # По описанию пытаемся понять
                if "keyboard" in lower_name or "клавиатур" in lower_name:
                    interfaces.append("keyboard")
                if "mouse" in lower_name or "мыш" in lower_name:
                    interfaces.append("mouse")

            is_keyboard = "keyboard" in interfaces
            is_mouse = "mouse" in interfaces

            vid, pid, serial = self._parse_usb_id(device_id or "")
            usb_path = getattr(dev, "LocationInformation", None)
            if usb_path:
                usb_path = usb_path.strip()

            # Ключ агрегации: vid:pid:serial_or_path
            key_serial = serial or usb_path or device_id or (name or "")
            key = f"{vid or 'NA'}:{pid or 'NA'}:{key_serial}"

            if key not in seen_keys:
                seen_keys[key] = HIDDevice(
                    vid=vid,
                    pid=pid,
                    serial=serial,
                    usb_path=usb_path,
                    name=name,
                    manufacturer=manufacturer,
                    description=description,
                    interfaces=[],
                    is_keyboard=is_keyboard,
                    is_mouse=is_mouse,
                    composite=False,
                )
            hid = seen_keys[key]

            # Объединяем интерфейсы
            for iface in interfaces:
                if iface not in hid.interfaces:
                    hid.interfaces.append(iface)
            hid.is_keyboard = hid.is_keyboard or is_keyboard
            hid.is_mouse = hid.is_mouse or is_mouse
            hid.composite = len(hid.interfaces) > 1

            # Если обнаружили другой порт, фиксируем usb_path как последний известный и помечаем composite для портов
            if usb_path and hid.usb_path and usb_path != hid.usb_path:
                # сохраняем последний путь, но можно позже расширить логирование
                hid.usb_path = usb_path
            elif usb_path and not hid.usb_path:
                hid.usb_path = usb_path

        hid_devices.extend(seen_keys.values())
        return hid_devices

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


