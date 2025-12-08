import logging
from typing import List

from domain.models import PeripheralDevice
from system.pnp_utils import (
    detect_connection_type,
    is_virtual_device,
    is_system_device,
)


def _add_peripheral(peripherals: List[PeripheralDevice], seen_devices: set,
                    category: str, name, manufacturer, description, connection_type,
                    device_id: str = None, pnp_class: str = None):
    if not name:
        return
    if is_virtual_device(name, device_id):
        return
    if is_system_device(name, pnp_class):
        return
    if device_id:
        if device_id in seen_devices:
            return
        seen_devices.add(device_id)
    else:
        key = f"{category}_{name}_{manufacturer or ''}"
        if key in seen_devices:
            return
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


def collect_peripherals(wmi_conn) -> List[PeripheralDevice]:
    peripherals: List[PeripheralDevice] = []
    seen_devices = set()

    pnp_devices_by_class = {}
    try:
        all_pnp_devices = wmi_conn.Win32_PnPEntity()
        for device in all_pnp_devices:
            pnp_class = getattr(device, "PNPClass", None)
            if pnp_class:
                pnp_devices_by_class.setdefault(pnp_class, []).append(device)
    except Exception as e:
        logging.warning(f"Не удалось получить PnP устройства: {e}")

    # Мониторы
    try:
        monitors_pnp = pnp_devices_by_class.get("Monitor", [])
        for pnp_mon in monitors_pnp:
            device_id = pnp_mon.DeviceID
            name = pnp_mon.Name.strip() if pnp_mon.Name else None
            manufacturer = pnp_mon.Manufacturer.strip() if pnp_mon.Manufacturer else None
            description = pnp_mon.Description.strip() if pnp_mon.Description else None
            connection_type = detect_connection_type(device_id, "Monitor")
            _add_peripheral(peripherals, seen_devices, "monitor", name, manufacturer, description, connection_type, device_id, "Monitor")

        try:
            desktop_monitors = wmi_conn.Win32_DesktopMonitor()
            for mon in desktop_monitors:
                device_id = getattr(mon, "DeviceID", None) or f"monitor_desktop_{len(peripherals)}"
                name = (mon.Name or mon.Caption or "").strip() or None
                manufacturer = getattr(mon, "MonitorManufacturer", None)
                manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer
                description = mon.Caption.strip() if mon.Caption else None
                connection_type = None
                _add_peripheral(peripherals, seen_devices, "monitor", name, manufacturer, description, connection_type, device_id, "Monitor")
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Ошибка получения информации о мониторах: {e}")

    # Клавиатуры
    try:
        keyboards_pnp = pnp_devices_by_class.get("Keyboard", [])
        for pnp_kb in keyboards_pnp:
            device_id = pnp_kb.DeviceID
            name = pnp_kb.Name.strip() if pnp_kb.Name else None
            manufacturer = pnp_kb.Manufacturer.strip() if pnp_kb.Manufacturer else None
            description = pnp_kb.Description.strip() if pnp_kb.Description else None
            connection_type = detect_connection_type(device_id, "Keyboard")
            _add_peripheral(peripherals, seen_devices, "keyboard", name, manufacturer, description, connection_type, device_id, "Keyboard")

        try:
            keyboards_wmi = wmi_conn.Win32_Keyboard()
            for kb in keyboards_wmi:
                device_id = getattr(kb, "DeviceID", None) or f"keyboard_wmi_{len(peripherals)}"
                name = kb.Description.strip() if kb.Description else None
                description = kb.Name.strip() if kb.Name else None
                connection_type = None
                _add_peripheral(peripherals, seen_devices, "keyboard", name, None, description, connection_type, device_id, "Keyboard")
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Ошибка получения информации о клавиатурах: {e}")

    # Мыши
    try:
        mice_pnp = pnp_devices_by_class.get("Mouse", [])
        for pnp_mouse in mice_pnp:
            device_id = pnp_mouse.DeviceID
            name = pnp_mouse.Name.strip() if pnp_mouse.Name else None
            manufacturer = pnp_mouse.Manufacturer.strip() if pnp_mouse.Manufacturer else None
            description = pnp_mouse.Description.strip() if pnp_mouse.Description else None
            connection_type = detect_connection_type(device_id, "Mouse")
            _add_peripheral(peripherals, seen_devices, "mouse", name, manufacturer, description, connection_type, device_id, "Mouse")

        try:
            mice_wmi = wmi_conn.Win32_PointingDevice()
            for pd in mice_wmi:
                device_id = getattr(pd, "DeviceID", None) or f"mouse_wmi_{len(peripherals)}"
                name = pd.Description.strip() if pd.Description else None
                description = pd.Name.strip() if pd.Name else None
                connection_type = None
                _add_peripheral(peripherals, seen_devices, "mouse", name, None, description, connection_type, device_id, "Mouse")
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Ошибка получения информации о мышах: {e}")

    # Принтеры
    try:
        for pr in wmi_conn.Win32_Printer():
            name = pr.Name.strip() if pr.Name else None
            manufacturer = getattr(pr, "Manufacturer", None)
            manufacturer = manufacturer.strip() if isinstance(manufacturer, str) else manufacturer

            description_parts = []
            if getattr(pr, "Location", None):
                description_parts.append(f"Location: {pr.Location.strip()}")
            if getattr(pr, "Comment", None):
                description_parts.append(pr.Comment.strip())
            if getattr(pr, "DriverName", None):
                description_parts.append(f"Driver: {pr.DriverName.strip()}")
            connection_type = None
            if getattr(pr, "PortName", None):
                port = pr.PortName.strip()
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
            _add_peripheral(peripherals, seen_devices, "printer", name, manufacturer, description, connection_type, device_id, "Printer")
    except Exception as e:
        logging.error(f"Ошибка получения информации о принтерах: {e}")

    # Камеры
    try:
        cameras = pnp_devices_by_class.get("Camera", [])
        for cam in cameras:
            device_id = cam.DeviceID
            name = cam.Name.strip() if cam.Name else None
            if name and ("scanner" in name.lower() or "сканер" in name.lower() or "wsd устройство сканирования" in name.lower()):
                continue
            manufacturer = cam.Manufacturer.strip() if cam.Manufacturer else None
            description = cam.Description.strip() if cam.Description else None
            connection_type = detect_connection_type(device_id, "Camera")
            _add_peripheral(peripherals, seen_devices, "camera", name, manufacturer, description, connection_type, device_id, "Camera")
    except Exception as e:
        logging.error(f"Ошибка получения информации о камерах: {e}")

    # Аудио
    try:
        audio_devices = pnp_devices_by_class.get("AudioEndpoint", []) + \
                        pnp_devices_by_class.get("Media", []) + \
                        pnp_devices_by_class.get("Sound", [])
        for audio in audio_devices:
            device_id = audio.DeviceID
            name = audio.Name.strip() if audio.Name else None
            if name and ("high definition audio" in name.lower() and any(mon in name.lower() for mon in ["nvidia", "amd", "intel"])):
                continue
            manufacturer = audio.Manufacturer.strip() if audio.Manufacturer else None
            description = audio.Description.strip() if audio.Description else None
            connection_type = detect_connection_type(device_id, "Audio")
            category = "audio"
            if name:
                lower = name.lower()
                if "microphone" in lower or "микрофон" in lower:
                    category = "microphone"
                elif "speaker" in lower or "headphone" in lower or "динамик" in lower or "наушник" in lower:
                    category = "speaker"
            _add_peripheral(peripherals, seen_devices, category, name, manufacturer, description, connection_type, device_id, "Audio")
    except Exception as e:
        logging.error(f"Ошибка получения информации об аудио устройствах: {e}")

    # Прочие USB/HID
    try:
        other_usb = pnp_devices_by_class.get("USB", []) + pnp_devices_by_class.get("HIDClass", [])
        for device in other_usb:
            device_id = device.DeviceID
            name = device.Name.strip() if device.Name else None
            pnp_class = getattr(device, "PNPClass", None)
            if is_system_device(name, pnp_class):
                continue
            if not name or is_virtual_device(name, device_id):
                continue
            name_lower = name.lower()
            if any(keyword in name_lower for keyword in ["keyboard", "клавиатур", "mouse", "мыш",
                                                         "monitor", "монитор", "printer", "принтер",
                                                         "camera", "камер", "audio", "аудио",
                                                         "scanner", "сканер"]):
                continue

            manufacturer = device.Manufacturer.strip() if device.Manufacturer else None
            description = device.Description.strip() if device.Description else None
            connection_type = detect_connection_type(device_id, "USB")
            _add_peripheral(peripherals, seen_devices, "other", name, manufacturer, description, connection_type, device_id, pnp_class)
    except Exception as e:
        logging.error(f"Ошибка получения информации о других USB устройствах: {e}")

    return peripherals

