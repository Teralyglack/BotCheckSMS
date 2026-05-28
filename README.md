# ChatDigest Bot - обработка переписок в Telegram

**ChatDigest Bot** - Python-проект для производственной практики. Бот принимает фрагмент переписки в Telegram: текст, голосовые сообщения, видеокружки, аудио, скрины и фото с текстом. После обработки он выдаёт результат в одном из форматов: дословная транскрипция, краткое содержание или тезисы.

Проект использует российский AI-стек:

- **GigaChat API** - краткое содержание и тезисы;
- **Yandex SpeechKit** - распознавание голосовых сообщений, аудио и видеокружков;
- **Yandex Vision OCR** - распознавание текста на фото и скринах;
- **SQLite** - история пользователей и обработанных переписок;
- **python-docx + ReportLab** - экспорт результата в DOCX и PDF;
- **Telegram Bot API** - интерфейс пользователя и админ-панель.

В папке `assets/` лежит готовая аватарка `bot_avatar.png`, которую можно поставить через BotFather.

---

## Возможности

### Для пользователя

- обработка до 20 сообщений за один запрос;
- приём текста, голосовых, видеокружков, аудио, фото и скринов;
- распознавание ролей участников переписки;
- выбор формата результата:
  - дословная транскрипция;
  - краткое содержание;
  - тезисы;
- история обработанных переписок через `/history`;
- повторное открытие сохранённого результата;
- экспорт результата в **DOCX** и **PDF**;
- улучшенный UX: понятное приветствие, кнопки, статусы обработки и более информативные ошибки.

### Для заказчика / администратора

Админ-панель находится **прямо в Telegram-боте**. Администратор пишет команду:

```text
/admin
```

После этого бот показывает статистику:

- количество пользователей;
- количество обработок;
- количество успешных и ошибочных обработок;
- сколько сообщений сохранено в истории;
- популярные форматы результата;
- типы входных данных: текст, голосовые, фото, аудио;
- последние обработки.

Доступ к `/admin` есть только у Telegram ID, указанных в переменной `ADMIN_IDS`.

---

## Структура проекта

```text
chat_digest_bot/
├── app/
│   ├── bot/
│   │   ├── handlers.py          # Telegram-команды, кнопки, сценарии пользователя и админа
│   │   └── keyboards.py         # Reply/Inline-клавиатуры
│   ├── domain/
│   │   └── models.py            # модели сообщений, сессий и форматов вывода
│   ├── services/
│   │   ├── database.py          # SQLite: пользователи, история, статистика
│   │   ├── exporter.py          # экспорт результатов в DOCX/PDF
│   │   ├── formatters.py        # транскрипция, подготовка текста
│   │   ├── gigachat_client.py   # клиент GigaChat API
│   │   ├── media.py             # загрузка файлов, ffmpeg, медиаобработка
│   │   ├── storage.py           # временная сессия текущего запроса
│   │   ├── yandex_auth.py       # авторизация Yandex API
│   │   ├── yandex_speechkit.py  # распознавание речи
│   │   └── yandex_vision.py     # OCR изображений
│   ├── config.py                # настройки из .env
│   └── main.py                  # точка входа
├── tests/                       # тесты
├── data/                        # SQLite-база создаётся автоматически
├── exports/                     # DOCX/PDF создаются автоматически
├── .env.example                 # пример настроек
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Быстрый запуск в PyCharm

### 1. Открыть проект

Распакуйте архив и откройте папку `chat_digest_bot` в PyCharm:

```text
File → Open → chat_digest_bot
```

Открывать нужно папку, где лежат `app`, `requirements.txt`, `.env.example`, `README.md`.

### 2. Создать виртуальное окружение

В PyCharm:

```text
File → Settings → Project → Python Interpreter → Add Interpreter → Virtualenv
```

Рекомендуемая версия Python: **3.11+**.

### 3. Установить зависимости

В терминале PyCharm:

```bash
pip install -r requirements.txt
```

### 4. Установить ffmpeg

`ffmpeg` нужен для голосовых сообщений и видеокружков.

Проверка:

```bash
ffmpeg -version
```

Если команда не найдена, на Windows можно установить так:

```bash
winget install -e --id Gyan.FFmpeg
```

После установки полностью перезапустите PyCharm.

### 5. Создать `.env`

Скопируйте `.env.example` в `.env` и заполните ключи:

```env
TELEGRAM_BOT_TOKEN=токен_от_BotFather
ADMIN_IDS=ваш_telegram_id

GIGACHAT_AUTH_KEY=ключ_gigachat_без_Basic
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat
GIGACHAT_OAUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_API_BASE_URL=https://gigachat.devices.sberbank.ru/api
GIGACHAT_VERIFY_SSL=false

YANDEX_IAM_TOKEN=
YANDEX_API_KEY=api_key_yandex
YANDEX_FOLDER_ID=folder_id_yandex

YANDEX_SPEECHKIT_LANG=ru-RU
YANDEX_SPEECHKIT_TOPIC=general
YANDEX_OCR_LANGUAGES=ru,en
YANDEX_OCR_MODEL=page
YANDEX_DATA_LOGGING_ENABLED=false

MAX_MESSAGES_PER_BATCH=20
TEMP_DIR=.tmp
LOG_LEVEL=INFO
DATABASE_PATH=data/bot.sqlite3
EXPORT_DIR=exports
```

Важно: для Yandex лучше использовать `YANDEX_API_KEY`, а `YANDEX_IAM_TOKEN` оставить пустым, потому что IAM-токен быстро истекает.

### 6. Запустить

В терминале PyCharm из корня проекта:

```bash
python -m app.main
```

Или настройте Run Configuration:

```text
Module name: app.main
Working directory: путь_к_chat_digest_bot
```

---

## Как пользоваться ботом

1. Напишите боту `/start`.
2. Перешлите сообщения или отправьте текст/голосовое/скрин.
3. Нажмите кнопку **✅ Готово**.
4. Выберите формат результата.
5. После получения результата используйте кнопки **DOCX** или **PDF**.
6. Команда `/history` откроет историю обработок.

---

## Где показывается админ-панель

Админ-панель не является отдельным сайтом. Для MVP она встроена в Telegram-бота.

Администратор пишет:

```text
/admin
```

Бот отвечает сообщением со статистикой и кнопкой обновления. Такой вариант удобен для практики, потому что не нужно разворачивать отдельный web-интерфейс, backend для сайта и авторизацию администратора.

Для будущей production-версии можно сделать отдельную web-панель на FastAPI + React, но для MVP Telegram-панель проще, надёжнее и быстрее демонстрируется на защите.

---

## Команды

```text
/start    - приветствие
/help     - инструкция
/new      - очистить текущий набор сообщений
/done     - выбрать формат результата
/history  - история обработанных переписок
/admin    - статистика для администратора
```

---

## Проверка проекта

```bash
python -m compileall app tests
pytest -q
```

---

## Работа бота 
<img width="589" height="1280" alt="photo_5242431949471685535_y" src="https://github.com/user-attachments/assets/43826d5b-ae6a-42b4-adf4-8b0d2b5e29e2" />

<img width="589" height="1280" alt="photo_5242431949471685536_y" src="https://github.com/user-attachments/assets/e10269b1-d769-4a7e-a725-9eb2dd7cffaf" />

<img width="962" height="1280" alt="photo_5242431949471685541_y" src="https://github.com/user-attachments/assets/eb8e8a4c-ec11-4b06-961f-3ae4f539908e" />

<img width="1280" height="684" alt="photo_5242431949471685540_y" src="https://github.com/user-attachments/assets/f2b5757a-aacb-4725-8747-1154ef36c7e9" />

<img width="589" height="1280" alt="photo_5242431949471685538_y" src="https://github.com/user-attachments/assets/be4a79dd-06a4-4339-8c6f-2cfacfa04603" />

<img width="589" height="1280" alt="photo_5242431949471685537_y" src="https://github.com/user-attachments/assets/c200c679-dbf6-485b-984a-ea152ccee96b" />

<img width="589" height="1280" alt="photo_5242431949471685542_y" src="https://github.com/user-attachments/assets/de0eb623-55e0-48b0-a43a-26e683f91742" />
