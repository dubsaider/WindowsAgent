import logging
from typing import List

from domain.models import HIDDevice
from system.pnp_utils import parse_usb_id


def collect_hid_devices(wmi_conn) -> List[HIDDevice]:
    """
    Агрегировать HID по физическому устройству:
    ключ = vid:pid + serial (если есть) + usb_path/bus-port
    """
    hid_devices: List[HIDDevice] = []
    seen_keys = {}

    pnp_hid = []
    try:
        all_pnp = wmi_conn.Win32_PnPEntity()
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

        interfaces = []
        lower_name = (name or "").lower()
        if pnp_class.lower() == "keyboard" or "keyboard" in lower_name or "клавиатур" in lower_name:
            interfaces.append("keyboard")
        if pnp_class.lower() == "mouse" or "mouse" in lower_name or "мыш" in lower_name:
            interfaces.append("mouse")
        if not interfaces and pnp_class.lower() == "hidclass":
            if "keyboard" in lower_name or "клавиатур" in lower_name:
                interfaces.append("keyboard")
            if "mouse" in lower_name or "мыш" in lower_name:
                interfaces.append("mouse")

        is_keyboard = "keyboard" in interfaces
        is_mouse = "mouse" in interfaces

        vid, pid, serial = parse_usb_id(device_id or "")
        usb_path = getattr(dev, "LocationInformation", None)
        if usb_path:
            usb_path = usb_path.strip()

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

        for iface in interfaces:
            if iface not in hid.interfaces:
                hid.interfaces.append(iface)
        hid.is_keyboard = hid.is_keyboard or is_keyboard
        hid.is_mouse = hid.is_mouse or is_mouse
        hid.composite = len(hid.interfaces) > 1

        if usb_path and hid.usb_path and usb_path != hid.usb_path:
            hid.usb_path = usb_path
        elif usb_path and not hid.usb_path:
            hid.usb_path = usb_path

    hid_devices.extend(seen_keys.values())
    return hid_devices

