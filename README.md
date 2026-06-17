# Booking Service

Небольшой сервис для записи на встречи. API принимает заявку, сохраняет бронь в статусе `pending` и отправляет ее в очередь. Дальше Celery-воркер асинхронно подтверждает бронь или переводит ее в `failed`, если сымитирован сбой внешнего сервиса.

Фронтенда здесь нет: я сосредоточился на backend-части, инфраструктуре, миграциях, фоновой обработке и тестах.

## Что внутри

- REST API на FastAPI
- PostgreSQL как основное хранилище
- SQLAlchemy ORM и Alembic для миграций
- Redis как broker и result backend для Celery
- Celery-воркер для обработки броней
- pytest-тесты, которые запускаются без Docker
- JSON-логи
- простой rate limiting на создание броней

## Запуск

Из корня проекта:

```bash
docker compose up --build
```

После старта:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

При запуске `web`-контейнер сначала применяет миграции Alembic, потом стартует FastAPI-приложение. Файл `.env` для первого запуска не обязателен: дефолтные значения уже прописаны в `docker-compose.yml`.

Если хочется переопределить настройки:

```bash
cp .env.example .env
```

Для старой standalone-версии Compose команда такая же по смыслу:

```bash
docker-compose up --build
```

## API

### Создать бронь

```http
POST /bookings
```

```json
{
  "name": "Anna",
  "datetime": "2026-07-01T10:00:00Z",
  "service_type": "consultation"
}
```

Пример через curl:

```bash
curl -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{"name":"Anna","datetime":"2026-07-01T10:00:00Z","service_type":"consultation"}'
```

Ответ возвращается сразу. Новая бронь получает статус `pending`, а подтверждение происходит уже в фоне.

### Получить бронь

```http
GET /bookings/{id}
```

Возвращает бронь и ее текущий статус: `pending`, `confirmed` или `failed`.

### Список броней

```http
GET /bookings?status=pending&limit=20&offset=0
```

`status` необязателен. Можно фильтровать по `pending`, `confirmed` и `failed`. Для пагинации используются `limit` и `offset`.

### Отменить бронь

```http
DELETE /bookings/{id}
```

Отменить можно только бронь в статусе `pending`. Если воркер уже успел ее обработать, API вернет `409 Conflict`.

## Как работает воркер

Основной сценарий такой:

1. API создает запись в БД со статусом `pending`.
2. В Celery отправляется задача с `booking_id`.
3. Воркер забирает бронь из БД.
4. Если бронь все еще `pending`, он пытается ее обработать.
5. При успехе статус меняется на `confirmed`, после этого логируется mock-уведомление.
6. При временном сбое задача уходит на retry с backoff.
7. Если попытки закончились, бронь переводится в `failed`.

Идемпотентность здесь завязана на статус. Воркер меняет только `pending`-бронь. Если задачу по тому же `booking_id` запустить повторно после `confirmed` или `failed`, она ничего не сломает и не отправит уведомление второй раз.

## Тесты

Тесты запускаются без PostgreSQL, Redis и Docker:

```bash
pip install -r requirements-dev.txt
pytest
```

Для тестов используется временная SQLite-база. Очередь в API-тестах мокается, чтобы не требовать запущенный Redis и Celery. Логика воркера проверяется отдельно: есть тест на успешное подтверждение, идемпотентный повторный запуск и перевод брони в `failed`.

## Почему так

**FastAPI** взял из-за простого REST API, встроенной OpenAPI-документации и нормальной валидации через Pydantic.

**SQLAlchemy ORM + Alembic** дают понятную модель данных и воспроизводимые миграции. В бизнес-логике нет прямых SQL-запросов.

**Celery + Redis** хорошо подходят для такого сценария: API быстро отвечает клиенту, а вся потенциально медленная обработка уезжает в фон.

**SQLite в тестах** нужен только для удобства локального запуска. В рабочем Docker-стеке используется PostgreSQL.

**Retry с backoff** добавлен потому, что сбой внешнего сервиса обычно временный. После последней неудачной попытки статус становится `failed`.

**Rate limiting** сделан простым in-memory вариантом. Для тестового сервиса этого достаточно; в production я бы вынес такой лимит в Redis или на уровень API gateway.

## Переменные окружения

Основные настройки лежат в `.env.example`:

- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `BOOKING_FAILURE_RATE`
- `POST_BOOKINGS_RATE_LIMIT_PER_MINUTE`
- `LOG_LEVEL`

## Структура проекта

```text
app/
  main.py          # REST API
  models.py        # SQLAlchemy models
  schemas.py       # Pydantic schemas
  tasks.py         # Celery worker logic
  database.py      # DB engine and sessions
  config.py        # settings
  logging.py       # JSON logging
  rate_limit.py    # simple in-memory rate limiter
alembic/
  versions/        # migrations
tests/             # pytest tests
```

## Команды

```bash
make dev
make test
make lint
```

`make lint` здесь запускает `compileall`. Отдельный линтер я не добавлял, чтобы не раздувать небольшое тестовое задание лишней конфигурацией.
