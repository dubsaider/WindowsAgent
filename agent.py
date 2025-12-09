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
from kafka_layer.update_consumer import UpdateNotificationConsumer
from system import WindowsHardwareCollector
from agent_core.state import AgentState, StateStore
from agent_core.hasher import calc_config_hash
from agent_core.logging_config import setup_logging
from agent_core.updater import UpdateChecker


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
        
        # Система обновлений
        self.update_checker = UpdateChecker(
            update_server_url=self.kafka_config.update_server_url,
            logger=self.logger
        )
        # Устанавливаем ссылку на агент для graceful shutdown при обновлении
        self.update_checker.set_agent_instance(self)
        self.update_check_interval = self.kafka_config.update_check_interval
        self.last_update_check = 0
        
        # Kafka consumer для обновлений (если указан топик)
        self.update_consumer: Optional[UpdateNotificationConsumer] = None
        if self.kafka_config.update_topic:
            try:
                self.update_consumer = UpdateNotificationConsumer(
                    config=self.kafka_config,
                    update_topic=self.kafka_config.update_topic,
                    callback=self._handle_update_notification
                )
            except Exception as e:
                self.logger.warning(f"Не удалось создать consumer обновлений: {e}")

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
    
    def _handle_update_notification(self, notification: dict):
        """Обработчик уведомлений об обновлениях из Kafka"""
        try:
            self.logger.info(f"Получено уведомление об обновлении из Kafka: {notification}")
            if self.update_checker.handle_kafka_update_notification(notification):
                # perform_seamless_update вызовет graceful shutdown, поэтому этот код
                # может не выполниться, но на всякий случай логируем
                self.logger.info("Незаметное обновление инициировано, агент будет завершён")
        except Exception as e:
            self.logger.error(f"Ошибка при обработке уведомления об обновлении: {e}")
    
    def _check_for_updates(self):
        """Проверяет наличие обновлений через HTTP, если прошло достаточно времени (fallback метод)"""
        if not self.update_checker.update_server_url:
            return
        
        now = time.time()
        if now - self.last_update_check >= self.update_check_interval:
            try:
                self.logger.debug("Проверка обновлений через HTTP...")
                if self.update_checker.update_if_available():
                    self.logger.warning("Обновление установлено. Перезапустите агент для применения изменений.")
            except Exception as e:
                self.logger.error(f"Ошибка при проверке обновлений: {e}")
            finally:
                self.last_update_check = now
    
    def run(self):
        """Запустить агент в режиме постоянной работы"""
        self.running = True
        self.logger.info("Запуск агента PC-Guardian...")
        
        # Запускаем Kafka consumer для обновлений, если настроен
        if self.update_consumer:
            try:
                self.update_consumer.start()
                self.logger.info(f"Consumer обновлений запущен (топик: {self.kafka_config.update_topic})")
            except Exception as e:
                self.logger.error(f"Не удалось запустить consumer обновлений: {e}")
        
        # Первое сканирование при запуске
        self.scan_and_send()
        
        # Периодическое сканирование
        while self.running:
            try:
                time.sleep(self.scan_interval)
                if self.running:
                    # Проверяем обновления через HTTP (fallback, если Kafka не используется)
                    if not self.update_consumer:
                        self._check_for_updates()
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
        if self.update_consumer:
            self.update_consumer.stop()
        if self.kafka_client:
            self.kafka_client.close()
        self.logger.info("Агент остановлен")


def _cleanup_old_exe_and_temp_files():
    """Очищает старые exe файлы и временные файлы обновлений при запуске"""
    import glob
    from pathlib import Path
    
    try:
        if getattr(sys, 'frozen', False):
            current_exe = Path(sys.executable).resolve()
        else:
            current_exe = Path(sys.argv[0]).resolve()
        
        current_dir = current_exe.parent
        
        # Ищем временные файлы обновлений (PCGuardianAgent_new_*.exe)
        temp_files = list(current_dir.glob("PCGuardianAgent_new_*.exe"))
        
        # Если мы запущены из временного файла, заменяем старый exe
        if "PCGuardianAgent_new_" in current_exe.name:
            old_exe = current_dir / "PCGuardianAgent.exe"
            if old_exe.exists():
                try:
                    # Создаём резервную копию старого
                    backup = old_exe.with_suffix('.exe.old')
                    if backup.exists():
                        backup.unlink()
                    old_exe.rename(backup)
                    
                    # Копируем новый exe на место старого
                    import shutil
                    shutil.copy2(current_exe, old_exe)
                    
                    # Удаляем временный файл
                    current_exe.unlink()
                except Exception as e:
                    logging.warning(f"Не удалось заменить старый exe: {e}")
        
        # Удаляем другие временные файлы обновлений
        for temp_file in temp_files:
            try:
                if temp_file != current_exe:
                    temp_file.unlink()
            except Exception:
                pass
        
        # Удаляем старые резервные копии (старше 7 дней)
        import time
        old_backups = list(current_dir.glob("PCGuardianAgent.exe.old"))
        for backup in old_backups:
            try:
                if time.time() - backup.stat().st_mtime > 7 * 24 * 3600:
                    backup.unlink()
            except Exception:
                pass
                
    except Exception as e:
        logging.debug(f"Ошибка при очистке временных файлов: {e}")


def main():
    """Точка входа для запуска агента"""
    import argparse
    
    # Очищаем временные файлы обновлений при запуске
    _cleanup_old_exe_and_temp_files()
    
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

