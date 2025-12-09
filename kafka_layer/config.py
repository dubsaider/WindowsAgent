"""
Конфигурация Kafka для системы PC-Guardian.
"""

import os
from typing import Optional


class KafkaConfig:
    """Класс для работы с конфигурацией Kafka"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Инициализация конфигурации Kafka.

        Args:
            config_file: Путь к файлу конфигурации (опционально)
        """

        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "10.53.16.49:9092"
        )
        self.topic = os.getenv("KAFKA_TOPIC", "pc-guardian-configs")
        self.security_protocol = os.getenv(
            "KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"
        )  # PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
        self.ssl_cafile = os.getenv("KAFKA_SSL_CAFILE", None)
        self.ssl_certfile = os.getenv("KAFKA_SSL_CERTFILE", None)
        self.ssl_keyfile = os.getenv("KAFKA_SSL_KEYFILE", None)
        self.sasl_mechanism = os.getenv(
            "KAFKA_SASL_MECHANISM", None
        )  # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
        self.sasl_username = os.getenv("KAFKA_SASL_USERNAME", None)
        self.sasl_password = os.getenv("KAFKA_SASL_PASSWORD", None)
        self.consumer_group = os.getenv(
            "KAFKA_CONSUMER_GROUP", "pc-guardian-server"
        )
        
        # URL сервера обновлений (опционально, для HTTP-based обновлений)
        self.update_server_url = os.getenv("UPDATE_SERVER_URL", None)
        self.update_check_interval = int(os.getenv("UPDATE_CHECK_INTERVAL", "3600"))  # По умолчанию 1 час
        
        # Топик Kafka для уведомлений об обновлениях (опционально)
        self.update_topic = os.getenv("UPDATE_TOPIC", "pc-guardian-updates")

        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)

        self._validate()

    def _load_from_file(self, config_file: str):
        """Загрузка конфигурации из файла"""
        import json

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.bootstrap_servers = config.get(
                    "bootstrap_servers", self.bootstrap_servers
                )
                self.topic = config.get("topic", self.topic)
                self.security_protocol = config.get(
                    "security_protocol", self.security_protocol
                )
                self.ssl_cafile = config.get("ssl_cafile", self.ssl_cafile)
                self.ssl_certfile = config.get("ssl_certfile", self.ssl_certfile)
                self.ssl_keyfile = config.get("ssl_keyfile", self.ssl_keyfile)
                self.sasl_mechanism = config.get(
                    "sasl_mechanism", self.sasl_mechanism
                )
                self.sasl_username = config.get(
                    "sasl_username", self.sasl_username
                )
                self.sasl_password = config.get(
                    "sasl_password", self.sasl_password
                )
                self.consumer_group = config.get(
                    "consumer_group", self.consumer_group
                )
                self.update_server_url = config.get(
                    "update_server_url", self.update_server_url
                )
                self.update_check_interval = config.get(
                    "update_check_interval", self.update_check_interval
                )
                self.update_topic = config.get(
                    "update_topic", self.update_topic
                )
        except Exception as e:
            print(f"Ошибка загрузки конфигурации Kafka: {e}")

    def _validate(self):
        """Базовая валидация конфигурации."""
        errors = []

        if not self.bootstrap_servers:
            errors.append("bootstrap_servers не задан")

        if not self.topic:
            errors.append("topic не задан")

        if not self.update_topic:
            errors.append("update_topic не задан")

        if self.update_check_interval and self.update_check_interval <= 0:
            errors.append("update_check_interval должен быть > 0")

        if errors:
            raise ValueError(f"Некорректная конфигурация Kafka: {', '.join(errors)}")

    def get_producer_config(self) -> dict:
        """Получить конфигурацию для Kafka Producer"""
        config = {
            "bootstrap_servers": self.bootstrap_servers,
            "security_protocol": self.security_protocol,
        }

        if self.security_protocol in ["SSL", "SASL_SSL"]:
            if self.ssl_cafile:
                config["ssl_cafile"] = self.ssl_cafile
            if self.ssl_certfile:
                config["ssl_certfile"] = self.ssl_certfile
            if self.ssl_keyfile:
                config["ssl_keyfile"] = self.ssl_keyfile

        if self.security_protocol in ["SASL_PLAINTEXT", "SASL_SSL"]:
            if self.sasl_mechanism:
                config["sasl_mechanism"] = self.sasl_mechanism
            if self.sasl_username:
                config["sasl_plain_username"] = self.sasl_username
            if self.sasl_password:
                config["sasl_plain_password"] = self.sasl_password

        return config

    def get_consumer_config(self) -> dict:
        """Получить конфигурацию для Kafka Consumer"""
        config = self.get_producer_config()
        config["group_id"] = self.consumer_group
        config["auto_offset_reset"] = "earliest"
        config["enable_auto_commit"] = True
        return config


