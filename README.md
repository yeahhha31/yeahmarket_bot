# yeahmarket_bot

## Запуск в Docker

1. Создайте бота через `@BotFather` и получите токен.
2. Откройте файл `.env` и вставьте токен в строку `BOT_TOKEN=`.
3. Соберите и запустите контейнер:

```bash
docker compose up -d --build
```

Для ссылок в кнопках можно задать `ORDER_URL`, `BARAHOLKA_URL`, `IOS_URL`, `ANDROID_URL` и `MANAGER_USERNAME`.

Посмотреть журнал: `docker compose logs -f bot`. Остановить: `docker compose down`.

Данные заявок, тем форума и счётчика сохраняются в Docker volume `bot-data`; команда `docker compose down` их не удаляет.

## Тесты

Тестовый набор использует только стандартную библиотеку Python и не выполняет запросов к Telegram или товарным сайтам:

```bash
python -m unittest discover -s tests -v
```

## Структура

- `main.py` — единственная точка запуска.
- `bot/config.py` — настройки и загрузка `.env`.
- `bot/telegram_api.py` — общий клиент Telegram Bot API.
- `bot/constants.py` — тексты кнопок и платформ.
- `bot/keyboards.py` — клавиатуры Telegram.
- `bot/state.py` — состояния диалога и данные пользователя.
- `bot/validation.py` — проверка ссылок на товары.
- `bot/forum.py` — темы форума, заявки и пересылка сообщений.
- `bot/handlers.py` — сценарии кнопок, заказов, вопросов и калькулятора.
- `bot/runtime.py` — polling и запуск приложения.

Калькулятор применяет формулу `CNY × 0.485 × 1.10` только для китайских площадок. Для USD/EUR и валюты другой площадки отображается введённая сумма без этой формулы.
