# Booking Service

Backend-сервис для записи на встречи: REST API создает бронь, Celery-воркер асинхронно подтверждает ее или переводит в `failed`, Redis используется как broker/result backend, PostgreSQL хранит данные.

## Запуск сервиса

1. При необходимости скопируйте переменные окружения, чтобы переопределить дефолты из `docker-compose.yml`:

```bash
cp .env.example .env
```

2. Поднимите стек:

```bash
docker compose up --build
```

При старте web-контейнер применяет миграции Alembic. API будет доступен на `http://localhost:8000`, Swagger UI: `http://localhost:8000/docs`.
Если у вас установлен standalone Compose, та же команда работает как `docker-compose up --build`.

## API

- `POST /bookings` - создать бронь.
- `GET /bookings/{id}` - получить статус брони.
- `GET /bookings?status=pending&limit=20&offset=0` - список броней с фильтром и пагинацией.
- `DELETE /bookings/{id}` - отменить бронь, если она еще `pending`.

Пример создания:

```bash
curl -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{"name":"Anna","datetime":"2026-07-01T10:00:00Z","service_type":"consultation"}'
```

## Тесты

Тесты не требуют Docker, PostgreSQL или Redis:

```bash
pip install -r requirements-dev.txt
pytest
```

В тестах используется временная SQLite-база, а отправка задачи в очередь мокается на уровне API. Логика воркера проверяется отдельно с мокнутой отправкой уведомления.

## Технические решения

- **FastAPI + Pydantic**: легкий REST API с автодокументацией и понятной валидацией входных данных.
- **SQLAlchemy ORM + Alembic**: ORM закрывает работу с хранилищем без прямого SQL, Alembic дает воспроизводимые миграции для PostgreSQL.
- **Celery + Redis**: классический стек для фоновой обработки; API только создает `pending`-бронь и ставит `booking_id` в очередь.
- **Идемпотентность воркера**: задача обрабатывает только `pending`-бронь. Если запись уже `confirmed` или `failed`, повторный запуск ничего не меняет и не отправляет повторное уведомление.
- **Retry с backoff**: имитация внешнего сбоя вызывает retry с экспоненциальной задержкой. Если попытки исчерпаны, бронь переводится в `failed`.
- **Structured logging**: приложение пишет JSON-логи с полями вроде `booking_id`, `status`, `service_type`.
- **Rate limiting**: `POST /bookings` ограничен простым in-memory лимитом на IP, значение задается через `POST_BOOKINGS_RATE_LIMIT_PER_MINUTE`.

## Структура

```text
app/
  main.py          # FastAPI routes
  models.py        # SQLAlchemy model and statuses
  schemas.py       # Pydantic schemas
  tasks.py         # Celery worker logic
  database.py      # engine/session setup
  config.py        # environment settings
alembic/           # migrations
tests/             # pytest suite
```
