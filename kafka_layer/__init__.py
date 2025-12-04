"""
Пакет для взаимодействия с Kafka (наш слой поверх библиотеки kafka-python).
"""

from .config import KafkaConfig  # noqa: F401
from .client import KafkaClient  # noqa: F401


