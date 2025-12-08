import logging
from typing import Optional, List

from domain.models import (
    Motherboard,
    CPU,
    RAMModule,
    Storage,
    GPU,
    NetworkAdapter,
    PSU,
)


def get_motherboard(wmi_conn) -> Optional[Motherboard]:
    try:
        board = wmi_conn.Win32_BaseBoard()[0]
        return Motherboard(
            serial_number=board.SerialNumber.strip() if board.SerialNumber else None,
            model=board.Product.strip() if board.Product else None,
            manufacturer=board.Manufacturer.strip() if board.Manufacturer else None,
            product=board.Product.strip() if board.Product else None,
        )
    except Exception as e:
        logging.error(f"Ошибка получения информации о материнской плате: {e}")
        return None


def get_cpu(wmi_conn) -> Optional[CPU]:
    try:
        cpu = wmi_conn.Win32_Processor()[0]
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


def get_ram_modules(wmi_conn) -> List[RAMModule]:
    modules: List[RAMModule] = []
    try:
        ram_list = wmi_conn.Win32_PhysicalMemory()
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


def get_storage_devices(wmi_conn) -> List[Storage]:
    devices: List[Storage] = []
    try:
        disks = wmi_conn.Win32_DiskDrive()
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


def get_gpu(wmi_conn) -> Optional[GPU]:
    try:
        gpus = wmi_conn.Win32_VideoController()
        for gpu in gpus:
            if "Intel" in (gpu.Name or ""):
                continue
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


def get_network_adapters(wmi_conn) -> List[NetworkAdapter]:
    adapters: List[NetworkAdapter] = []
    try:
        nics = wmi_conn.Win32_NetworkAdapterConfiguration(IPEnabled=True)
        for nic in nics:
            if nic.MACAddress:
                ip_addresses = list(nic.IPAddress) if getattr(nic, "IPAddress", None) else None
                subnets = list(nic.IPSubnet) if getattr(nic, "IPSubnet", None) else None
                gateways = list(nic.DefaultIPGateway) if getattr(nic, "DefaultIPGateway", None) else None
                dns_servers = list(nic.DNSServerSearchOrder) if getattr(nic, "DNSServerSearchOrder", None) else None

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


def get_psu(wmi_conn) -> Optional[PSU]:
    """Информация о БП обычно недоступна через стандартный WMI."""
    return None

