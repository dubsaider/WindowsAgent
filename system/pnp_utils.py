import logging
import re
from typing import Optional


def parse_usb_id(device_id: str):
    """Извлечь VID/PID/serial из PNPDeviceID."""
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


def detect_connection_type(device_id: str, pnp_class: str) -> Optional[str]:
    """Определить тип подключения устройства."""
    if not device_id:
        return None

    device_id_upper = device_id.upper()
    pnp_class_upper = (pnp_class or "").upper()

    if "USB" in device_id_upper or "USB\\" in device_id_upper:
        if "BLUETOOTH" in device_id_upper:
            return "Bluetooth"
        return "USB"

    if "BLUETOOTH" in device_id_upper or "BTH" in device_id_upper:
        return "Bluetooth"

    if "PS/2" in device_id_upper or "PS2" in device_id_upper or "PNP03" in device_id_upper:
        return "PS/2"

    if "MONITOR" in pnp_class_upper:
        if "DISPLAYPORT" in device_id_upper or "DP" in device_id_upper:
            return "DisplayPort"
        if "HDMI" in device_id_upper:
            return "HDMI"
        if "DVI" in device_id_upper:
            return "DVI"
        if "VGA" in device_id_upper:
            return "VGA"

    if "NETWORK" in device_id_upper or "TCP" in device_id_upper or "HTTP" in device_id_upper:
        return "Network"

    return None


def is_virtual_device(name: str, device_id: str = None) -> bool:
    """Проверка, является ли устройство виртуальным."""
    if not name:
        return False
    name_lower = name.lower()
    virtual_patterns = [
        "virtual", "виртуальн",
        "vmware", "virtualbox", "hyper-v",
        "remote desktop", "rdp",
        "microsoft virtual", "microsoft remote",
        "microsoft print to pdf",
        "microsoft xps document writer",
        "onenote",
    ]
    return any(pattern in name_lower for pattern in virtual_patterns)


def is_system_device(name: str, pnp_class: str = None) -> bool:
    """Проверка, является ли устройство системным (не периферией)."""
    if not name:
        return False
    name_lower = name.lower()
    pnp_class_lower = (pnp_class or "").lower()

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


def normalize_device_name(name: str) -> str:
    """Нормализация названия устройства для сравнения."""
    if not name:
        return ""
    normalized = name.lower()
    prefixes = ["generic", "универсальный", "стандартный", "standard"]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    normalized = re.sub(r'\s*\(\([^)]+\)\)', '', normalized)
    normalized = re.sub(r'\s*\([^)]*стандарт[^)]*\)', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()

