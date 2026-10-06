# Архитектура проекта Sugar Mommy Bot

## Дерево модулей

```
Sugar Mommy 2.0/
├── db/                          # Слой данных
│   ├── models/                  # SQLAlchemy 2.0 ORM-модели
│   ├── repositories/            # Доступ к БД (запросы, транзакции)
│   ├── session.py               # Async engine / session factory
│   └── alembic/                 # Миграции Alembic
├── backend/                     # Прикладной слой (бот)
│   ├── config.py                # pydantic-settings (.env)
│   ├── main.py                  # Точка входа
│   ├── bot/
│   │   ├── factory.py           # Сборка Dispatcher, роутеров
│   │   ├── middlewares/         # i18n, роли, throttling, логи
│   │   ├── filters/             # IsAdmin, IsMaster, ...
│   │   ├── keyboards/           # Inline-клавиатуры
│   │   ├── states/              # FSM (запись, блокировка, рассылка)
│   │   └── handlers/            # client / master / admin / common
│   ├── services/                # Бизнес-логика
│   └── scheduler/               # APScheduler: напоминания, waitlist, рассылки
├── locales/                     # ru / uz / en (.po → .mo)
├── scripts/compile_locales.py
├── docker-compose.yml
└── Dockerfile
```

## Поток данных

```
Handler (FSM) → Service → Repository → SQLAlchemy → PostgreSQL/SQLite
                    ↓
              Scheduler (отложенные задачи)
```

## FSM-сценарии (MVP)

### Запись клиента (`BookingStates`)
| Состояние | Действие |
|-----------|----------|
| `choosing_service` | Пагинация услуг |
| `choosing_master` | Мастера по услуге |
| `choosing_date` | Календарь 14 дней |
| `choosing_time` | Свободные слоты |
| `waitlist_offer` | Предложение очереди |
| `confirming` | Итог + правило 2 ч |

### Перенос (`RescheduleStates`)
`select_appointment` → `choosing_date` → `choosing_time` → `confirming`

### Блокировка слотов (`BlockSlotStates`)
`select_master` (админ) → `select_date` → `select_slots` → `confirm`

### Экстренная рассылка (`EmergencyBroadcastStates`)
`select_date` → `enter_text` → `confirm`

### Массовая рассылка (`MassBroadcastStates`)
`enter_text` → `enter_media` (опц.) → `confirm`

### Лист ожидания (клиент)
Callback `waitlist:*` без длинного FSM; подтверждение оффера — inline.

## Middleware

1. **DbSessionMiddleware** — `AsyncSession` в `data["session"]`
2. **UserMiddleware** — upsert User, `data["user"]`
3. **I18nMiddleware** — язык из User.language_code
4. **RoleMiddleware** — `data["role"]`: client | master | admin
5. **ThrottlingMiddleware** — анти-flood на callback/message
6. **LoggingMiddleware** — structlog JSON

## Scheduler (APScheduler AsyncIOScheduler)

| Job | Триггер | Действие |
|-----|---------|----------|
| `confirm_visit_reminders` | cron каждые 5 мин | Напоминание за 3 ч до визита |
| `unconfirmed_visit_alerts` | cron каждые 5 мин | Алерт админу за 1.5 ч без ответа |
| `repeat_visit_reminders` | cron каждый час | Отправка repeat_visit из Reminder |
| `complete_past_appointments` | cron каждые 15 мин | status → completed, план repeat |
| `waitlist_timeouts` | cron каждую минуту | expired offered → следующий в очереди |
| `broadcast_queue` | interval | Очередь массовой рассылки ≤30/сек |

## Фаза 2 (только план, код по сигналу)

### 1. Реактивация «спящих» клиентов
- **Модель**: `ReactivationCampaign` (service_id, days_after_last_visit, template_i18n, enabled).
- **Сервис**: `SleepingClientService` — nightly job: `last_completed_visit + N < today`, нет будущих записей, `User.is_active`.
- **Scheduler**: один cron (ночь), батчи с rate limit как у mass broadcast.
- **Handler**: deep-link «Записаться» с preselected service.

### 2. «Горящие окна» (Flash Sale)
- **Модели**: `FlashPromo` (date, discount_percent, master_id nullable), `FlashSlot` (master_id, date, start_time, promo_price).
- **Сервис**: `FlashSaleService` — слоты today/tomorrow со скидкой; атомарное бронирование.
- **UI**: пункт главного меню; админ CRUD скидок; опционально кнопка канала.

### 3. Сегментированная рассылка
- **FSM**: фильтры master / service / last_visit_from-to / has_future_appointment.
- **Repository**: динамический SQL по сегменту.
- **BroadcastLog.type**: добавить `segmented`.
