"""
Общие модули для системы PC-Guardian
"""
from .models import (
    HardwareComponent,
    Motherboard,
    CPU,
    RAMModule,
    Storage,
    GPU,
    NetworkAdapter,
    PSU,
    PCConfiguration,
    ChangeEvent
)
from .kafka_config import KafkaConfig

__all__ = [
    'HardwareComponent',
    'Motherboard',
    'CPU',
    'RAMModule',
    'Storage',
    'GPU',
    'NetworkAdapter',
    'PSU',
    'PCConfiguration',
    'ChangeEvent',
    'KafkaConfig'
]

