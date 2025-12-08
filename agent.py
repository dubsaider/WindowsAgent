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
import json
import hashlib
import os
from typing import Optional

from domain.models import PCConfiguration
from kafka_layer import KafkaConfig, KafkaClient
from system import WindowsHardwareCollector


class PCGuardianAgent:
    """Основной класс агента PC-Guardian для Windows"""
    
    def __init__(self, config_file: Optional[str] = None, scan_interval: int = 180, heartbeat_interval: int = 1800):
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
        self.state_file = "pc_guardian_state.json"
        self.heartbeat_interval = heartbeat_interval  # секунд между «пульсами» даже без изменений
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pc_guardian_agent.log', encoding='utf-8'),
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
        self.kafka_client.send_configuration(config)

    # ----- Отправка только при изменении конфигурации -----
    def _calc_config_hash(self, config: PCConfiguration) -> str:
        """Детерминированный хеш полной конфигурации"""
        payload = config.to_dict()
        payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Не удалось прочитать состояние: {e}")
            return {}

    def _save_state(self, hash_value: str, last_sent_ts: float):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({"last_hash": hash_value, "last_sent_ts": last_sent_ts}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить состояние: {e}")
    
    def scan_and_send(self):
        """Сканировать конфигурацию и отправить в Kafka"""
        try:
            self.logger.info("Начало сканирования конфигурации...")
            config = self.collector.collect_configuration()
            config_hash = self._calc_config_hash(config)
            state = self._load_state()
            last_hash = state.get("last_hash")
            last_sent_ts = state.get("last_sent_ts")
            now = time.time()

            if last_hash == config_hash:
                # Нет изменений — проверяем, не пора ли отправить heartbeat
                if last_sent_ts and (now - last_sent_ts) < self.heartbeat_interval:
                    self.logger.info("Изменений нет — отправка пропущена (таймер heartbeat еще не истек)")
                    return
                self.logger.info("Изменений нет — отправляем heartbeat-состояние")
            else:
                self.logger.info(f"Конфигурация собрана для PC: {config.pc_id} (обнаружены изменения)")

            self._send_configuration(config)
            self._save_state(config_hash, now)
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

