## PC-Guardian Windows Agent

Агент для Windows, собирающий информацию о комплектующих ПК, периферии и сетевых/сетевых параметрах и отправляющий её в Kafka.

Архитектура разбита на слои:
- `os_layer.py` — работа с ОС и WMI, сбор «сырой» информации о железе и периферии;
- `kafka_layer.py` — обёртка над KafkaProducer, отвечает только за отправку сообщений;
- `common/models.py` — общие датаклассы для описания конфигурации ПК;
- `agent.py` — доменный слой/оркестратор, который по расписанию запрашивает данные у `os_layer` и передаёт их в `kafka_layer`.

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

## Автоматическое обновление через Kafka

Агент поддерживает автоматическую установку обновлений через Kafka. Это позволяет централизованно распространять новые версии без ручного копирования exe файлов на каждое устройство.

### Как это работает

1. Агенты подписываются на топик Kafka для уведомлений об обновлениях
2. Когда выходит новая версия, администратор отправляет уведомление в Kafka
3. Все агенты получают уведомление и автоматически:
   - Скачивают новую версию exe
   - Запускают новую версию с теми же параметрами
   - Gracefully завершают старую версию
4. **Обновление происходит незаметно для пользователя** - без прерывания работы агента

### Создание топика Kafka

Перед использованием необходимо создать топик в Kafka:

```bash
python -m update_server.create_topic --config config.json
```

Или вручную через kafka-topics.sh:
```bash
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic pc-guardian-updates \
  --partitions 1 \
  --replication-factor 1
```

**Примечание:** Kafka может автоматически создать топик при первой записи (если включен `auto.create.topics.enable`), но рекомендуется создавать топики вручную для контроля конфигурации.

### Настройка агентов

Добавьте в `config.json` на каждом агенте:

```json
{
  "bootstrap_servers": "10.53.16.49:9092",
  "topic": "pc-guardian-configs",
  "update_topic": "pc-guardian-updates"
}
```

Параметры:
- `update_topic` - топик Kafka для уведомлений об обновлениях (по умолчанию `pc-guardian-updates`)

Или используйте переменную окружения:
```bash
set UPDATE_TOPIC=pc-guardian-updates
```

### Настройка сервера для хостинга exe файлов

Вам нужен HTTP сервер для размещения exe файлов. Можно использовать:

1. **Простой Python сервер** (из проекта):
   ```bash
   python -m update_server.server --port 8000 --exe-dir ../dist
   ```

2. **Любой веб-сервер** (nginx, apache, IIS) - просто разместите exe файл в директории веб-сервера

3. **Облачное хранилище** (S3, Azure Blob, Google Cloud Storage) с публичным доступом

### Процесс обновления

1. **Соберите новую версию:**
   ```bash
   build_agent.bat
   ```

2. **Обновите версию в `__version__.py`:**
   ```python
   __version__ = "1.5.0"
   ```

3. **Разместите exe файл на HTTP сервере:**
   - Скопируйте `dist/PCGuardianAgent.exe` на сервер
   - Убедитесь, что файл доступен по HTTP URL

4. **Отправьте уведомление в Kafka:**
   ```bash
   python -m update_server.send_notification \
     --config config.json \
     --version 1.5.0 \
     --download-url http://your-server:8000/updates/PCGuardianAgent.exe
   ```

   Или без конфига:
   ```bash
   python -m update_server.send_notification \
     --update-topic pc-guardian-updates \
     --version 1.5.0 \
     --download-url http://your-server:8000/updates/PCGuardianAgent.exe
   ```

5. **Агенты автоматически:**
   - Получат уведомление из Kafka
   - Скачают новый exe файл во временный файл
   - Запустят новую версию с теми же параметрами
   - Gracefully завершат старую версию
   - Новая версия заменит старый exe при запуске
   
   **Обновление происходит незаметно - без прерывания работы!**

### Альтернативный способ: HTTP polling (fallback)

Если вы предпочитаете периодическую проверку через HTTP вместо Kafka, можно использовать старый метод:

```json
{
  "update_server_url": "http://your-update-server:8000/updates",
  "update_check_interval": 3600
}
```

Агент будет периодически проверять наличие обновлений на HTTP сервере.

**Примечание:** При использовании Kafka обновление происходит автоматически и незаметно. При использовании HTTP polling после установки обновления агент нужно перезапустить вручную (или настроить автоматический перезапуск через службу Windows).

