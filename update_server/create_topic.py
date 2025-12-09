"""
Скрипт для создания топика Kafka для уведомлений об обновлениях.

Использование:
    python -m update_server.create_topic
    python -m update_server.create_topic --config ../config.json
    python -m update_server.create_topic --topic pc-guardian-updates --partitions 3 --replication-factor 1
"""

import argparse
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь для импорта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kafka_layer import KafkaConfig
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError


def create_update_topic(
    config_file: str = None,
    topic_name: str = None,
    num_partitions: int = 1,
    replication_factor: int = 1
):
    """Создаёт топик Kafka для уведомлений об обновлениях"""
    
    # Загружаем конфигурацию Kafka
    kafka_config = KafkaConfig(config_file)
    
    # Определяем имя топика
    if not topic_name:
        topic_name = kafka_config.update_topic
    
    if not topic_name:
        print("✗ Ошибка: не указан топик обновлений. Используйте --topic или добавьте update_topic в config.json")
        sys.exit(1)
    
    # Создаём admin client
    admin_config = kafka_config.get_producer_config()
    admin_client = KafkaAdminClient(**admin_config)
    
    try:
        # Создаём топик
        topic = NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor
        )
        
        print(f"Создание топика '{topic_name}'...")
        print(f"  Partitions: {num_partitions}")
        print(f"  Replication factor: {replication_factor}")
        print(f"  Bootstrap servers: {kafka_config.bootstrap_servers}")
        
        admin_client.create_topics([topic])
        print(f"✓ Топик '{topic_name}' успешно создан")
        
    except TopicAlreadyExistsError:
        print(f"ℹ Топик '{topic_name}' уже существует")
    except Exception as e:
        print(f"✗ Ошибка при создании топика: {e}")
        sys.exit(1)
    finally:
        admin_client.close()


def main():
    parser = argparse.ArgumentParser(
        description='Создание топика Kafka для уведомлений об обновлениях'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Путь к файлу конфигурации Kafka (опционально)'
    )
    parser.add_argument(
        '--topic',
        type=str,
        default=None,
        help='Имя топика (по умолчанию из конфига или "pc-guardian-updates")'
    )
    parser.add_argument(
        '--partitions',
        type=int,
        default=1,
        help='Количество партиций (по умолчанию 1)'
    )
    parser.add_argument(
        '--replication-factor',
        type=int,
        default=1,
        help='Фактор репликации (по умолчанию 1)'
    )
    
    args = parser.parse_args()
    
    create_update_topic(
        config_file=args.config,
        topic_name=args.topic,
        num_partitions=args.partitions,
        replication_factor=args.replication_factor
    )


if __name__ == '__main__':
    main()

