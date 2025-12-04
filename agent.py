"""
Агент для Windows - сбор данных о ПК и отправка в Kafka.

Слоистая архитектура:
- os_layer: взаимодействие с ОС/WMI
- common.kafka_config: конфигурация Kafka
- этот модуль: доменный «агент», который оркестрирует сбор и отправку
"""

import sys
import time
import logging
from typing import Optional

from domain.models import PCConfiguration
from kafka_layer import KafkaConfig, KafkaClient
from system import WindowsHardwareCollector


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
        # Слой ОС / WMI
        self.collector = WindowsHardwareCollector()

        # Слой Kafka
        self.kafka_config = KafkaConfig(config_file)
        self.kafka_client = KafkaClient(self.kafka_config)
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
        """Совместимость со старым интерфейсом: делегируем в kafka_layer."""
        # Оставлено для обратной совместимости. Новому коду лучше вызывать kafka_client напрямую.
        return
    
    def _send_configuration(self, config: PCConfiguration):
        """Отправить конфигурацию в Kafka"""
        # Вся логика отправки инкапсулирована в KafkaClient
        self.kafka_client.send_configuration(config)
    
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
        if self.kafka_client:
            self.kafka_client.close()
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

