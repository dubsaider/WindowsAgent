"""
Слой взаимодействия с Kafka.

Содержит обёртку над KafkaProducer, не знает ничего про WMI/ОС.
"""

import json
import logging
from typing import Any, Dict, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from kafka_layer.config import KafkaConfig
from domain.models import PCConfiguration


class KafkaClient:
    """Клиент Kafka для отправки конфигураций ПК."""

    def __init__(self, config: Optional[KafkaConfig] = None):
        self.logger = logging.getLogger(__name__)
        self.kafka_config = config or KafkaConfig()
        self.producer: Optional[KafkaProducer] = None

    def _create_producer(self):
        cfg = self.kafka_config.get_producer_config()
        self.producer = KafkaProducer(
            **cfg,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            retries=5,
            acks="all",
            request_timeout_ms=30000,
        )
        self.logger.info("Kafka Producer создан (kafka_layer.client)")

    def send_configuration(self, config: PCConfiguration):
        """Отправить конфигурацию ПК в Kafka."""
        if not self.producer:
            try:
                self._create_producer()
            except Exception as e:
                self.logger.error(f"Не удалось создать Kafka Producer: {e}")
                raise

        try:
            data: Dict[str, Any] = config.to_dict()
            future = self.producer.send(
                self.kafka_config.topic,
                value=data,
                key=config.pc_id.encode("utf-8"),
            )
            meta = future.get(timeout=10)
            self.logger.info(
                f"Конфигурация отправлена: PC={config.pc_id}, "
                f"Topic={meta.topic}, Partition={meta.partition}, Offset={meta.offset}"
            )
        except KafkaError as e:
            self.logger.error(f"Ошибка отправки в Kafka: {e}")
            self.producer = None
            raise
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при отправке в Kafka: {e}")
            raise

    def close(self):
        if self.producer:
            self.producer.close()
            self.producer = None


