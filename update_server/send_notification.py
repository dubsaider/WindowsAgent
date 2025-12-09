"""
Скрипт для отправки уведомления о новой версии агента в Kafka.

Использование:
    python -m update_server.send_notification --version 1.5.0 --download-url http://server:8000/updates/PCGuardianAgent.exe
    python -m update_server.send_notification --config ../config.json --version 1.5.0 --download-url http://server:8000/updates/PCGuardianAgent.exe
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Добавляем корневую директорию проекта в путь для импорта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kafka_layer import KafkaConfig
from kafka import KafkaProducer


def send_update_notification(
    config_file: Optional[str],
    update_topic: str,
    version: str,
    download_url: str,
    checksum: Optional[str] = None
):
    """Отправляет уведомление об обновлении в Kafka"""
    
    # Загружаем конфигурацию Kafka
    kafka_config = KafkaConfig(config_file)
    
    # Создаём producer
    producer_config = kafka_config.get_producer_config()
    producer = KafkaProducer(
        **producer_config,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        retries=5,
        acks="all"
    )
    
    # Формируем сообщение об обновлении
    update_message = {
        "version": version,
        "download_url": download_url,
        "type": "agent_update"
    }
    if checksum:
        update_message["checksum"] = checksum
    
    try:
        # Отправляем сообщение в топик обновлений
        future = producer.send(
            update_topic,
            value=update_message,
            key=b"update_notification"  # Все агенты получат это сообщение
        )
        
        # Ждём подтверждения
        metadata = future.get(timeout=30)
        print(f"✓ Уведомление об обновлении отправлено:")
        print(f"  Версия: {version}")
        print(f"  URL: {download_url}")
        print(f"  Топик: {metadata.topic}")
        print(f"  Partition: {metadata.partition}")
        print(f"  Offset: {metadata.offset}")
        print(f"\nВсе агенты получат это уведомление и обновятся до версии {version}")
        
    except Exception as e:
        print(f"✗ Ошибка при отправке уведомления: {e}")
        sys.exit(1)
    finally:
        producer.close()


def main():
    parser = argparse.ArgumentParser(
        description='Отправка уведомления о новой версии агента в Kafka'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Путь к файлу конфигурации Kafka (опционально)'
    )
    parser.add_argument(
        '--update-topic',
        type=str,
        default=None,
        help='Топик для уведомлений об обновлениях (по умолчанию из конфига или "pc-guardian-updates")'
    )
    parser.add_argument(
        '--version',
        type=str,
        required=True,
        help='Версия обновления (например, 1.5.0)'
    )
    parser.add_argument(
        '--download-url',
        type=str,
        required=True,
        help='URL для скачивания exe файла (например, http://server:8000/updates/PCGuardianAgent.exe)'
    )
    parser.add_argument(
        '--checksum',
        type=str,
        required=False,
        help='SHA256 для файла обновления (опционально)'
    )
    
    args = parser.parse_args()
    
    # Определяем топик обновлений
    if args.update_topic:
        update_topic = args.update_topic
    else:
        kafka_config = KafkaConfig(args.config)
        update_topic = kafka_config.update_topic
    
    if not update_topic:
        print("✗ Ошибка: не указан топик обновлений. Используйте --update-topic или добавьте update_topic в config.json")
        sys.exit(1)
    
    send_update_notification(
        config_file=args.config,
        update_topic=update_topic,
        version=args.version,
        download_url=args.download_url,
        checksum=args.checksum
    )


if __name__ == '__main__':
    main()

