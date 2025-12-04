"""
Доменный слой: модели и структуры данных, не зависящие от ОС и Kafka.
"""

from .models import (  # noqa: F401
    HardwareComponent,
    Motherboard,
    CPU,
    RAMModule,
    Storage,
    GPU,
    NetworkAdapter,
    PSU,
    PCConfiguration,
    ChangeEvent,
    PeripheralDevice,
)


