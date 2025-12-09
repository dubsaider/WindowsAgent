# Сервер обновлений PC-Guardian Agent

## Быстрый старт

### 1. Запуск сервера обновлений

После сборки exe файла (`build_agent.bat`), запустите сервер:

```bash
python -m update_server.server --port 8000 --exe-dir ../dist
```

Сервер будет доступен по адресу `http://localhost:8000` и предоставит:
- `http://localhost:8000/updates/version.json` - информация о версии
- `http://localhost:8000/updates/PCGuardianAgent.exe` - скачивание exe

### 2. Создание топика Kafka (один раз)

Перед первым использованием создайте топик в Kafka:

```bash
python -m update_server.create_topic --config ../config.json
```

Или вручную:
```bash
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic pc-guardian-updates \
  --partitions 1 \
  --replication-factor 1
```

**Примечание:** Kafka может автоматически создать топик при первой записи, но рекомендуется создавать вручную.

### 3. Отправка уведомления об обновлении в Kafka

После размещения нового exe файла на сервере, отправьте уведомление:

```bash
python -m update_server.send_notification \
  --config ../config.json \
  --version 1.5.0 \
  --download-url http://your-server:8000/updates/PCGuardianAgent.exe
```

### 4. Настройка агентов

Добавьте в `config.json` на каждом агенте:

```json
{
  "update_topic": "pc-guardian-updates"
}
```

Агенты будут автоматически получать уведомления об обновлениях из Kafka и обновляться незаметно.

## Процесс обновления

1. Соберите новую версию: `build_agent.bat`
2. Обновите версию в `__version__.py`
3. Скопируйте новый `dist/PCGuardianAgent.exe` в директорию сервера
4. Отправьте уведомление в Kafka через `send_notification.py`
5. Агенты автоматически обнаружат, скачают и установят обновление

## Альтернативные варианты размещения

### Вариант 1: Статический веб-сервер (nginx/apache)

Разместите файлы в директории веб-сервера:
- `version.json` - информация о версии
- `PCGuardianAgent.exe` - exe файл

Настройте URL в конфигурации агентов.

### Вариант 2: Облачное хранилище

Используйте S3, Azure Blob Storage или Google Cloud Storage с публичным доступом:
- Загрузите `version.json` и `PCGuardianAgent.exe`
- Укажите публичные URL в конфигурации агентов

### Вариант 3: Внутренний файловый сервер

Если у вас есть внутренний файловый сервер, разместите файлы там и настройте HTTP доступ.

## Безопасность

Для продакшена рекомендуется:
- Использовать HTTPS вместо HTTP
- Добавить аутентификацию на сервере обновлений
- Подписывать exe файлы цифровой подписью
- Использовать проверку целостности файлов (checksum)

