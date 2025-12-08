import logging
from typing import Optional

from domain.models import SystemInfo


def collect_system_info(wmi_conn) -> Optional[SystemInfo]:
    """Получить инфраструктурную информацию о системе."""
    try:
        computer_system = wmi_conn.Win32_ComputerSystem()[0]

        domain = computer_system.Domain.strip() if computer_system.Domain else None
        workgroup = computer_system.Workgroup.strip() if computer_system.Workgroup else None
        part_of_domain = computer_system.PartOfDomain if hasattr(computer_system, "PartOfDomain") else None

        domain_role = None
        if hasattr(computer_system, "DomainRole"):
            role = computer_system.DomainRole
            role_map = {
                0: "Standalone Workstation",
                1: "Member Workstation",
                2: "Standalone Server",
                3: "Member Server",
                4: "Backup Domain Controller",
                5: "Primary Domain Controller",
            }
            domain_role = role_map.get(role, f"Unknown ({role})")

        manufacturer = computer_system.Manufacturer.strip() if computer_system.Manufacturer else None
        model = computer_system.Model.strip() if computer_system.Model else None
        system_type = computer_system.SystemType.strip() if computer_system.SystemType else None

        total_memory = computer_system.TotalPhysicalMemory
        total_memory_gb = round(int(total_memory) / (1024 ** 3), 2) if total_memory else None

        os_info = wmi_conn.Win32_OperatingSystem()[0]
        os_name = os_info.Caption.strip() if os_info.Caption else None
        os_version = os_info.Version.strip() if os_info.Version else None
        os_build = os_info.BuildNumber.strip() if os_info.BuildNumber else None
        os_architecture = os_info.OSArchitecture.strip() if hasattr(os_info, "OSArchitecture") and os_info.OSArchitecture else None

        os_install_date = None
        if hasattr(os_info, "InstallDate") and os_info.InstallDate:
            try:
                install_date_str = str(os_info.InstallDate)
                if len(install_date_str) >= 8:
                    year = install_date_str[0:4]
                    month = install_date_str[4:6]
                    day = install_date_str[6:8]
                    os_install_date = f"{year}-{month}-{day}"
            except Exception:
                pass

        logged_in_user = None
        try:
            if hasattr(os_info, "RegisteredUser") and os_info.RegisteredUser:
                logged_in_user = os_info.RegisteredUser.strip()
        except Exception:
            pass

        timezone = None
        try:
            if hasattr(os_info, "CurrentTimeZone"):
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

