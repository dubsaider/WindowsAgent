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
from agent_core.state import AgentState, StateStore
from agent_core.hasher import calc_config_hash
from agent_core.logging_config import setup_logging


class PCGuardianAgent:
    """Основной класс агента PC-Guardian для Windows"""

    def __init__(self, config_file: Optional[str] = None, scan_interval: int = 180, heartbeat_interval: int = 1800):
        """
        Args:
            config_file: Путь к файлу конфигурации Kafka
            scan_interval: Интервал сканирования в секундах (по умолчанию 180)
            heartbeat_interval: Интервал принудительной отправки без изменений (по умолчанию 1800)
        """
        self.scan_interval = scan_interval
        self.heartbeat_interval = heartbeat_interval

        # Слой ОС / WMI
        self.collector = WindowsHardwareCollector()

        # Слой Kafka
        self.kafka_config = KafkaConfig(config_file)
        self.kafka_client = KafkaClient(self.kafka_config)
        self.running = False

        # Состояние
        self.state_file = "pc_guardian_state.json"
        # Логирование
        self.logger = setup_logging()
        self.state_store = StateStore(self.state_file, self.logger)

    def _create_producer(self):
        """Совместимость со старым интерфейсом: делегируем в kafka_layer."""
        return

    def _send_configuration(self, config: PCConfiguration):
        self.kafka_client.send_configuration(config)

    def _should_send(self, config_hash: str, state: AgentState) -> bool:
        now = time.time()
        if state.last_hash != config_hash:
            return True
        if state.last_sent_ts and (now - state.last_sent_ts) < self.heartbeat_interval:
            return False
        return True

    def scan_and_send(self):
        """Сканировать конфигурацию и отправить при изменении или по таймеру heartbeat."""
        try:
            self.logger.info("Начало сканирования конфигурации...")
            config = self.collector.collect_configuration()
            config_hash = calc_config_hash(config)
            state = self.state_store.load()

            if not self._should_send(config_hash, state):
                self.logger.info("Изменений нет — отправка пропущена (heartbeat не истек)")
                return

            if state.last_hash == config_hash:
                self.logger.info("Изменений нет — отправляем heartbeat-состояние")
            else:
                self.logger.info(f"Конфигурация собрана для PC: {config.pc_id} (обнаружены изменения)")

            self._send_configuration(config)
            self.state_store.save(AgentState(last_hash=config_hash, last_sent_ts=time.time()))
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
    parser.add_argument('--heartbeat', type=int, default=1800, help='Интервал heartbeat в секундах (по умолчанию 1800 = 30 минут)')
    parser.add_argument('--once', action='store_true', help='Выполнить одно сканирование и выйти')
    
    args = parser.parse_args()
    
    agent = PCGuardianAgent(config_file=args.config, scan_interval=args.interval, heartbeat_interval=args.heartbeat)
    
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

