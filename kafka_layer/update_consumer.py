"""
Kafka Consumer для получения уведомлений об обновлениях агента.
"""

import json
import logging
import threading
from typing import Optional, Callable
from queue import Queue, Empty

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from kafka_layer.config import KafkaConfig


class UpdateNotificationConsumer:
    """Consumer для прослушивания уведомлений об обновлениях из Kafka"""
    
    def __init__(self, config: KafkaConfig, update_topic: str, callback: Callable[[dict], None]):
        """
        Args:
            config: Конфигурация Kafka
            update_topic: Топик для уведомлений об обновлениях
            callback: Функция, вызываемая при получении уведомления об обновлении
        """
        self.config = config
        self.update_topic = update_topic
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def _create_consumer(self):
        """Создаёт Kafka Consumer для прослушивания обновлений"""
        cfg = self.config.get_consumer_config()
        # Используем уникальный group_id для обновлений
        cfg['group_id'] = f"{self.config.consumer_group}-updates"
        cfg['auto_offset_reset'] = 'latest'  # Читаем только новые сообщения
        cfg['enable_auto_commit'] = True
        cfg['consumer_timeout_ms'] = 1000  # Таймаут для возможности проверки running
        
        self.consumer = KafkaConsumer(
            self.update_topic,
            **cfg,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        self.logger.info(f"Kafka Consumer для обновлений создан (топик: {self.update_topic})")
    
    def _consume_loop(self):
        """Основной цикл потребления сообщений"""
        try:
            while self.running:
                try:
                    # Получаем сообщения с таймаутом для возможности проверки running
                    message_pack = self.consumer.poll(timeout_ms=1000)
                    
                    if not message_pack:
                        continue
                    
                    for topic_partition, messages in message_pack.items():
                        for message in messages:
                            try:
                                update_info = message.value
                                self.logger.info(f"Получено уведомление об обновлении: {update_info}")
                                self.callback(update_info)
                            except Exception as e:
                                self.logger.error(f"Ошибка обработки сообщения об обновлении: {e}")
                                
                except KafkaError as e:
                    self.logger.error(f"Ошибка Kafka при получении обновлений: {e}")
                    # Пересоздаём consumer при ошибке
                    if self.consumer:
                        try:
                            self.consumer.close()
                        except Exception:
                            pass
                    self.consumer = None
                    if self.running:
                        try:
                            self._create_consumer()
                        except Exception as e2:
                            self.logger.error(f"Не удалось пересоздать consumer: {e2}")
                            # Пауза перед повтором
                            import time
                            time.sleep(5)
                except Exception as e:
                    self.logger.error(f"Неожиданная ошибка в цикле потребления: {e}")
                    import time
                    time.sleep(5)
                    
        except Exception as e:
            self.logger.error(f"Критическая ошибка в цикле потребления: {e}")
        finally:
            if self.consumer:
                try:
                    self.consumer.close()
                except Exception:
                    pass
                self.consumer = None
    
    def start(self):
        """Запускает consumer в отдельном потоке"""
        if self.running:
            self.logger.warning("Consumer уже запущен")
            return
        
        try:
            self._create_consumer()
            self.running = True
            self.thread = threading.Thread(target=self._consume_loop, daemon=True)
            self.thread.start()
            self.logger.info("Consumer обновлений запущен")
        except Exception as e:
            self.logger.error(f"Не удалось запустить consumer: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Останавливает consumer"""
        self.running = False
        if self.consumer:
            try:
                self.consumer.close()
            except Exception:
                pass
            self.consumer = None
        # Из callback может вызываться stop из того же потока.
        # Чтобы не получить "cannot join current thread", проверяем.
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Consumer обновлений остановлен")

