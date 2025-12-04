"""
Агент для Windows - сбор данных о комплектующих ПК и отправка в Kafka
"""
import sys
import os
import time
import socket
import json
import logging
from pathlib import Path
from typing import Optional

# Импорт общих модулей из локальной директории
from common.models import (
    PCConfiguration, Motherboard, CPU, RAMModule, Storage, GPU, NetworkAdapter, PSU
)
from common.kafka_config import KafkaConfig

try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError
except ImportError:
    print("Ошибка: Не установлен kafka-python. Установите: pip install kafka-python")
    sys.exit(1)

try:
    import wmi
except ImportError:
    print("Ошибка: Не установлен WMI. Установите: pip install WMI")
    sys.exit(1)


class WindowsHardwareCollector:
    """Класс для сбора информации о комплектующих в Windows"""
    
    def __init__(self):
        self.wmi_conn = wmi.WMI()
        self.hostname = socket.gethostname()
    
    def get_pc_id(self) -> str:
        """Получить уникальный идентификатор ПК"""
        try:
            # Используем серийный номер материнской платы + имя ПК
            motherboard = self.wmi_conn.Win32_BaseBoard()[0]
            serial = motherboard.SerialNumber.strip()
            if serial and serial != "To be filled by O.E.M.":
                return f"{serial}_{self.hostname}"
            else:
                # Если серийный номер недоступен, используем UUID системы
                system = self.wmi_conn.Win32_ComputerSystemProduct()[0]
                uuid = system.UUID
                return f"{uuid}_{self.hostname}"
        except Exception as e:
            logging.error(f"Ошибка получения PC ID: {e}")
            return f"UNKNOWN_{self.hostname}"
    
    def get_motherboard(self) -> Optional[Motherboard]:
        """Получить информацию о материнской плате"""
        try:
            board = self.wmi_conn.Win32_BaseBoard()[0]
            return Motherboard(
                serial_number=board.SerialNumber.strip() if board.SerialNumber else None,
                model=board.Product.strip() if board.Product else None,
                manufacturer=board.Manufacturer.strip() if board.Manufacturer else None,
                product=board.Product.strip() if board.Product else None
            )
        except Exception as e:
            logging.error(f"Ошибка получения информации о материнской плате: {e}")
            return None
    
    def get_cpu(self) -> Optional[CPU]:
        """Получить информацию о процессоре"""
        try:
            cpu = self.wmi_conn.Win32_Processor()[0]
            return CPU(
                serial_number=None,  # В Windows обычно недоступен
                model=cpu.Name.strip() if cpu.Name else None,
                manufacturer=cpu.Manufacturer.strip() if cpu.Manufacturer else None,
                name=cpu.Name.strip() if cpu.Name else None,
                cores=cpu.NumberOfCores if cpu.NumberOfCores else None,
                threads=cpu.NumberOfLogicalProcessors if cpu.NumberOfLogicalProcessors else None
            )
        except Exception as e:
            logging.error(f"Ошибка получения информации о процессоре: {e}")
            return None
    
    def get_ram_modules(self) -> list[RAMModule]:
        """Получить информацию о модулях оперативной памяти"""
        modules = []
        try:
            ram_list = self.wmi_conn.Win32_PhysicalMemory()
            for idx, ram in enumerate(ram_list):
                size_gb = None
                if ram.Capacity:
                    size_gb = int(ram.Capacity) // (1024 ** 3)
                
                module = RAMModule(
                    serial_number=ram.SerialNumber.strip() if ram.SerialNumber else None,
                    model=ram.PartNumber.strip() if ram.PartNumber else None,
                    size_gb=size_gb,
                    slot=ram.DeviceLocator.strip() if ram.DeviceLocator else f"Slot{idx}",
                    speed=f"{ram.Speed}MHz" if ram.Speed else None,
                    manufacturer=ram.Manufacturer.strip() if ram.Manufacturer else None
                )
                modules.append(module)
        except Exception as e:
            logging.error(f"Ошибка получения информации о RAM: {e}")
        return modules
    
    def get_storage_devices(self) -> list[Storage]:
        """Получить информацию о накопителях"""
        devices = []
        try:
            # Получаем физические диски
            disks = self.wmi_conn.Win32_DiskDrive()
            for disk in disks:
                size_gb = None
                if disk.Size:
                    size_gb = int(disk.Size) // (1024 ** 3)
                
                # Определяем тип интерфейса
                interface = disk.InterfaceType.strip() if disk.InterfaceType else None
                storage_type = "HDD"
                if "SSD" in (disk.MediaType or "").upper() or "SSD" in (disk.Model or "").upper():
                    storage_type = "SSD"
                if "NVMe" in (disk.InterfaceType or "").upper() or "NVMe" in (disk.Model or "").upper():
                    storage_type = "NVMe"
                    interface = "NVMe"
                
                device = Storage(
                    serial_number=disk.SerialNumber.strip() if disk.SerialNumber else None,
                    model=disk.Model.strip() if disk.Model else None,
                    size_gb=size_gb,
                    interface=interface,
                    type=storage_type
                )
                devices.append(device)
        except Exception as e:
            logging.error(f"Ошибка получения информации о накопителях: {e}")
        return devices
    
    def get_gpu(self) -> Optional[GPU]:
        """Получить информацию о видеокарте"""
        try:
            gpus = self.wmi_conn.Win32_VideoController()
            # Берем первую дискретную видеокарту (не встроенную)
            for gpu in gpus:
                # Пропускаем встроенные видеокарты Intel
                if "Intel" in (gpu.Name or ""):
                    continue
                
                memory_gb = None
                if gpu.AdapterRAM:
                    memory_gb = int(gpu.AdapterRAM) // (1024 ** 3)
                
                return GPU(
                    serial_number=None,  # В Windows обычно недоступен через WMI
                    model=gpu.Name.strip() if gpu.Name else None,
                    manufacturer=gpu.AdapterCompatibility.strip() if gpu.AdapterCompatibility else None,
                    name=gpu.Name.strip() if gpu.Name else None,
                    memory_gb=memory_gb
                )
        except Exception as e:
            logging.error(f"Ошибка получения информации о видеокарте: {e}")
        return None
    
    def get_network_adapters(self) -> list[NetworkAdapter]:
        """Получить информацию о сетевых адаптерах"""
        adapters = []
        try:
            nics = self.wmi_conn.Win32_NetworkAdapterConfiguration(IPEnabled=True)
            for nic in nics:
                if nic.MACAddress:
                    adapter = NetworkAdapter(
                        mac_address=nic.MACAddress.strip(),
                        name=nic.Description.strip() if nic.Description else None,
                        manufacturer=None  # Можно получить через Win32_NetworkAdapter
                    )
                    adapters.append(adapter)
        except Exception as e:
            logging.error(f"Ошибка получения информации о сетевых адаптерах: {e}")
        return adapters
    
    def get_psu(self) -> Optional[PSU]:
        """Получить информацию о блоке питания (обычно недоступно через WMI)"""
        # В Windows информация о БП обычно недоступна через стандартные API
        return None
    
    def collect_configuration(self) -> PCConfiguration:
        """Собрать полную конфигурацию ПК"""
        pc_id = self.get_pc_id()
        
        config = PCConfiguration(
            pc_id=pc_id,
            hostname=self.hostname,
            motherboard=self.get_motherboard(),
            cpu=self.get_cpu(),
            ram_modules=self.get_ram_modules(),
            storage_devices=self.get_storage_devices(),
            gpu=self.get_gpu(),
            network_adapters=self.get_network_adapters(),
            psu=self.get_psu()
        )
        
        return config


class PCGuardianAgent:
    """Основной класс агента PC-Guardian для Windows"""
    
    def __init__(self, config_file: Optional[str] = None, scan_interval: int = 180):
        """
        Инициализация агента
        
        Args:
            config_file: Путь к файлу конфигурации Kafka
            scan_interval: Интервал сканирования в секундах (по умолчанию 180 секунд = 3 минуты)
        """
        self.scan_interval = scan_interval
        self.collector = WindowsHardwareCollector()
        self.kafka_config = KafkaConfig(config_file)
        self.producer = None
        self.running = False
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pc_guardian_agent.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_producer(self):
        """Создать Kafka Producer"""
        try:
            config = self.kafka_config.get_producer_config()
            self.producer = KafkaProducer(
                **config,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                retries=5,
                acks='all',
                request_timeout_ms=30000
            )
            self.logger.info("Kafka Producer создан успешно")
        except Exception as e:
            self.logger.error(f"Ошибка создания Kafka Producer: {e}")
            raise
    
    def _send_configuration(self, config: PCConfiguration):
        """Отправить конфигурацию в Kafka"""
        try:
            if not self.producer:
                self._create_producer()
            
            data = config.to_dict()
            future = self.producer.send(
                self.kafka_config.topic,
                value=data,
                key=config.pc_id.encode('utf-8')
            )
            
            # Ждем подтверждения
            record_metadata = future.get(timeout=10)
            self.logger.info(
                f"Конфигурация отправлена: PC={config.pc_id}, "
                f"Topic={record_metadata.topic}, "
                f"Partition={record_metadata.partition}, "
                f"Offset={record_metadata.offset}"
            )
        except KafkaError as e:
            self.logger.error(f"Ошибка отправки в Kafka: {e}")
            # Пересоздаем producer при ошибке
            self.producer = None
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при отправке: {e}")
    
    def scan_and_send(self):
        """Сканировать конфигурацию и отправить в Kafka"""
        try:
            self.logger.info("Начало сканирования конфигурации...")
            config = self.collector.collect_configuration()
            self.logger.info(f"Конфигурация собрана для PC: {config.pc_id}")
            self._send_configuration(config)
        except Exception as e:
            self.logger.error(f"Ошибка при сканировании: {e}")
    
    def run(self):
        """Запустить агент в режиме постоянной работы"""
        self.running = True
        self.logger.info("Запуск агента PC-Guardian...")
        
        # Первое сканирование при запуске
        self.scan_and_send()
        
        # Периодическое сканирование
        while self.running:
            try:
                time.sleep(self.scan_interval)
                if self.running:
                    self.scan_and_send()
            except KeyboardInterrupt:
                self.logger.info("Получен сигнал остановки")
                self.stop()
            except Exception as e:
                self.logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(60)  # Пауза перед повтором
    
    def stop(self):
        """Остановить агент"""
        self.running = False
        if self.producer:
            self.producer.close()
        self.logger.info("Агент остановлен")


def main():
    """Точка входа для запуска агента"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PC-Guardian Agent для Windows')
    parser.add_argument('--config', type=str, help='Путь к файлу конфигурации Kafka')
    parser.add_argument('--interval', type=int, default=180, help='Интервал сканирования в секундах (по умолчанию 180 = 3 минуты)')
    parser.add_argument('--once', action='store_true', help='Выполнить одно сканирование и выйти')
    
    args = parser.parse_args()
    
    agent = PCGuardianAgent(config_file=args.config, scan_interval=args.interval)
    
    try:
        if args.once:
            agent.scan_and_send()
        else:
            agent.run()
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

