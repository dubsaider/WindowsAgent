# PC-Guardian Windows Agent

Агент для Windows, собирающий информацию о комплектующих ПК и отправляющий её в Kafka.

## Установка

1. Установите Python 3.8 или выше
2. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Конфигурация

Скопируйте `config.json.example` в `config.json` и настройте параметры подключения к Kafka:

```json
{
  "bootstrap_servers": "kafka-server:9092",
  "topic": "pc-guardian-configs",
  "security_protocol": "PLAINTEXT"
}
```

Для использования SSL/TLS:
```json
{
  "bootstrap_servers": "kafka-server:9093",
  "topic": "pc-guardian-configs",
  "security_protocol": "SSL",
  "ssl_cafile": "path/to/ca-cert",
  "ssl_certfile": "path/to/client-cert",
  "ssl_keyfile": "path/to/client-key"
}
```

Для использования SASL:
```json
{
  "bootstrap_servers": "kafka-server:9092",
  "topic": "pc-guardian-configs",
  "security_protocol": "SASL_PLAINTEXT",
  "sasl_mechanism": "SCRAM-SHA-256",
  "sasl_username": "username",
  "sasl_password": "password"
}
```

Также можно использовать переменные окружения:
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC`
- `KAFKA_SECURITY_PROTOCOL`
- и т.д.

## Использование

### Одноразовое сканирование:
```bash
python agent.py --once
```

### Постоянная работа:
```bash
python agent.py --interval 180
```

Где `--interval` - интервал сканирования в секундах (по умолчанию 180 = 3 минуты).

### С указанием конфигурации:
```bash
python agent.py --config config.json --interval 1800
```

## Сборка в один EXE (PyInstaller)

Для дистрибуции агента без установки Python можно собрать одиночный exe-файл.

1. Убедитесь, что зависимости установлены:
```bash
pip install -r requirements.txt
```

2. Запустите скрипт сборки для Windows:
```bash
build_agent.bat
```

Он:
- установит/обновит `pyinstaller`,
- соберёт exe по спецификации `build_agent.spec`,
- положит результат в директорию `dist\PCGuardianAgent.exe`.

3. На целевой машине достаточно:
- скопировать `PCGuardianAgent.exe`,
- положить рядом `config.json` (по образцу `config.json.example`),
- запустить (по умолчанию каждые 3 минуты):
```bash
PCGuardianAgent.exe --config config.json
```

## Установка как служба Windows

Для установки агента как службы Windows можно использовать NSSM (Non-Sucking Service Manager) или создать службу вручную.

### Использование NSSM:

1. Скачайте NSSM: https://nssm.cc/download
2. Установите службу:
```bash
nssm install PCGuardianAgent "C:\Python\python.exe" "C:\path\to\agent.py"
nssm set PCGuardianAgent AppParameters "--config C:\path\to\config.json --interval 3600"
nssm start PCGuardianAgent
```

## Логирование

Логи сохраняются в файл `pc_guardian_agent.log` в директории запуска агента.

