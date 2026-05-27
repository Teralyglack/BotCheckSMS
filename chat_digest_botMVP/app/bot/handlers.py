from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.bot.keyboards import (
    admin_keyboard,
    history_keyboard,
    main_reply_keyboard,
    output_format_keyboard,
    result_actions_keyboard,
)
from app.config import Settings
from app.domain.models import OutputFormat
from app.services.database import DatabaseService, HistoryRecord
from app.services.errors import MissingCredentialsError
from app.services.exporter import ResultExporter
from app.services.formatters import build_transcript, split_for_telegram
from app.services.gigachat_client import GigaChatService
from app.services.media import MediaProcessor, UnsupportedMessageError
from app.services.storage import InMemorySessionStore

logger = logging.getLogger(__name__)

FORMAT_NAMES = {
    "transcript": "Транскрипция",
    "summary": "Краткое содержание",
    "bullets": "Тезисы",
}

KIND_NAMES = {
    "text": "текст",
    "voice": "голосовое",
    "video_note": "видеокружок",
    "photo": "фото/скрин",
    "document_image": "изображение",
    "audio": "аудио",
}

WELCOME_TEXT = """
👋 Привет! Я ChatDigest Bot.

Я помогаю быстро разобрать переписку:
📝 текстовые сообщения
🎙 голосовые
📹 видеокружки
🖼 скрины и фото с текстом

Как пользоваться:
1. Перешлите мне до 20 сообщений из любого чата.
2. Нажмите «✅ Готово».
3. Выберите формат результата: транскрипция, краткое содержание или тезисы.

Дополнительно:
📚 /history — история обработок и скачивание DOCX/PDF
🧹 /new — начать заново
❓ /help — помощь
""".strip()

HELP_TEXT = """
❓ Как пользоваться ботом

1. Перешлите сюда сообщения из Telegram-чата.
2. Можно отправлять текст, голосовые, видеокружки, аудио и скрины.
3. Максимум для MVP — 20 сообщений за один запрос.
4. Когда всё отправили, нажмите «✅ Готово».
5. Выберите нужный результат:
   📄 дословная транскрипция;
   🧠 краткое содержание;
   📌 тезисы.

После обработки результат сохраняется в историю. Его можно открыть снова или скачать в DOCX/PDF.
""".strip()


@dataclass(slots=True)
class HandlerDeps:
    settings: Settings
    store: InMemorySessionStore
    media_processor: MediaProcessor
    ai: GigaChatService
    db: DatabaseService
    exporter: ResultExporter


def get_user_id(update: Update) -> int | None:
    user = update.effective_user
    return user.id if user else None


def is_admin(settings: Settings, user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.admin_ids


def remember_user(update: Update, deps: HandlerDeps) -> None:
    user = update.effective_user
    if not user:
        return
    deps.db.upsert_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global Telegram error handler.

    It prevents the bot from crashing on unexpected Telegram/API errors and writes
    the real reason to the console log.
    """
    logger.exception("Unhandled Telegram bot error", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла внутренняя ошибка бота. Попробуйте ещё раз или начните заново через /new."
            )
        except Exception as exc:
            logger.debug("Could not send error message to user: %s", exc)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    await update.effective_message.reply_text(WELCOME_TEXT, reply_markup=main_reply_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    await update.effective_message.reply_text(HELP_TEXT, reply_markup=main_reply_keyboard())


async def new_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    user_id = get_user_id(update)
    if user_id is not None:
        deps.store.clear(user_id)
    await update.effective_message.reply_text(
        "🧹 Текущий набор очищен. Перешлите новую переписку.",
        reply_markup=main_reply_keyboard(),
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    user_id = get_user_id(update)
    if user_id is None:
        return

    session = deps.store.get(user_id)
    if not session.messages:
        await update.effective_message.reply_text("Пока нет сообщений. Перешлите переписку и нажмите «Готово».")
        return

    await update.effective_message.reply_text(
        f"✅ Принято сообщений: {len(session.messages)}.\n\nВ каком формате выдать результат?",
        reply_markup=output_format_keyboard(),
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    user_id = get_user_id(update)
    if user_id is None:
        return
    await send_history(update.effective_message, deps, user_id)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    user_id = get_user_id(update)
    if not is_admin(deps.settings, user_id):
        await update.effective_message.reply_text("⛔ Админ-панель доступна только администратору проекта.")
        return
    await update.effective_message.reply_text(format_admin_stats(deps.db.get_admin_stats()), reply_markup=admin_keyboard())


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    remember_user(update, deps)
    message = update.effective_message
    user_id = get_user_id(update)
    if not message or user_id is None:
        return

    text = (message.text or "").strip().lower()
    if text in {"✅ готово", "готово"}:
        await done(update, context)
        return
    if text in {"🧹 очистить", "очистить"}:
        await new_batch(update, context)
        return
    if text in {"ℹ️ помощь", "помощь"}:
        await help_command(update, context)
        return
    if text in {"📚 история", "история"}:
        await history_command(update, context)
        return

    session = deps.store.get(user_id)
    if len(session.messages) >= deps.settings.max_messages_per_batch:
        await message.reply_text(
            f"⚠️ Лимит MVP — {deps.settings.max_messages_per_batch} сообщений. Нажмите /done, чтобы получить результат."
        )
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    status = processing_status(message)
    status_message = None
    if status:
        status_message = await message.reply_text(status)

    role = session.resolve_role(extract_forward_sender_name(message))
    try:
        extracted = await deps.media_processor.process(message=message, role=role)
    except UnsupportedMessageError as exc:
        await message.reply_text(str(exc))
        return
    except MissingCredentialsError as exc:
        await message.reply_text(f"⚠️ Не хватает настроек API.\n\n{exc}")
        return
    except RuntimeError as exc:
        logger.exception("Failed to process message")
        await message.reply_text(f"⚠️ Не удалось обработать медиафайл.\n\nПричина: {exc}")
        return
    except Exception:
        logger.exception("Failed to process message")
        await message.reply_text(
            "⚠️ Не получилось обработать это сообщение.\n\n"
            "Проверьте формат файла, ключи Yandex API и качество изображения/аудио."
        )
        return

    if status_message:
        try:
            await status_message.delete()
        except Exception as exc:  # UI cleanup is optional.
            logger.debug("Ignored Telegram UI cleanup error: %s", exc)

    if extracted.is_empty():
        await message.reply_text(
            "⚠️ Сообщение принято, но текст не распознан. Попробуйте прислать файл/скрин в лучшем качестве."
        )
        return

    session.add(extracted)
    count = len(session.messages)
    kind_name = KIND_NAMES.get(extracted.kind.value, extracted.kind.value)
    if count >= deps.settings.max_messages_per_batch:
        await message.reply_text(
            f"✅ Добавлено: {count}/{deps.settings.max_messages_per_batch}. Достигнут лимит.\n\nВыберите формат результата:",
            reply_markup=output_format_keyboard(),
        )
    else:
        await message.reply_text(
            f"✅ Добавлено: {count}/{deps.settings.max_messages_per_batch}\n"
            f"Тип: {kind_name}\n"
            f"Автор: {extracted.role}\n\n"
            "Можно переслать ещё или нажать «✅ Готово».",
            reply_markup=main_reply_keyboard(),
        )


async def on_format_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    deps.db.upsert_user(query.from_user.id, query.from_user.username, query.from_user.full_name)
    session = deps.store.get(query.from_user.id)
    if not session.messages:
        await query.edit_message_text("Текущий набор пуст. Перешлите сообщения заново.")
        return

    _, raw_format = query.data.split(":", 1)
    output_format = OutputFormat(raw_format)
    await query.edit_message_text("🧠 Готовлю результат...")

    try:
        if output_format == OutputFormat.TRANSCRIPT:
            result = build_transcript(session.messages)
        else:
            result = await deps.ai.summarize(session.messages, output_format)
        request_id = deps.db.create_success_request(
            telegram_id=query.from_user.id,
            output_format=output_format,
            result_text=result,
            messages=session.messages,
        )
    except MissingCredentialsError as exc:
        deps.db.create_failed_request(query.from_user.id, raw_format, str(exc), session.messages)
        await query.message.reply_text(f"⚠️ Не хватает настроек API.\n\n{exc}")
        return
    except Exception as exc:
        deps.db.create_failed_request(query.from_user.id, raw_format, str(exc), session.messages)
        logger.exception("Failed to build result")
        await query.message.reply_text(
            "⚠️ Не получилось подготовить результат. Попробуйте ещё раз или выберите другой формат."
        )
        return

    for chunk in split_for_telegram(result):
        await query.message.reply_text(chunk)
    await query.message.reply_text(
        f"✅ Результат сохранён в историю под номером #{request_id}.\n"
        "Его можно скачать в DOCX/PDF или открыть позже через /history.",
        reply_markup=result_actions_keyboard(request_id),
    )


async def on_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    deps.db.upsert_user(query.from_user.id, query.from_user.username, query.from_user.full_name)

    if query.data == "history:list":
        await send_history(query.message, deps, query.from_user.id)
        return

    _, action, raw_id = query.data.split(":", 2)
    if action != "open" or not raw_id.isdigit():
        await query.message.reply_text("Неизвестное действие истории.")
        return

    request_id = int(raw_id)
    record_data = deps.db.get_request(request_id)
    if not record_data:
        await query.message.reply_text("Запись истории не найдена.")
        return
    record, _messages = record_data
    if record.user_id != query.from_user.id and not is_admin(deps.settings, query.from_user.id):
        await query.message.reply_text("⛔ Эта запись истории принадлежит другому пользователю.")
        return

    header = format_history_record_header(record)
    for chunk in split_for_telegram(f"{header}\n\n{record.result_text}"):
        await query.message.reply_text(chunk)
    await query.message.reply_text("Скачать результат:", reply_markup=result_actions_keyboard(record.request_id))


async def on_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    deps.db.upsert_user(query.from_user.id, query.from_user.username, query.from_user.full_name)

    _, file_type, raw_id = query.data.split(":", 2)
    if file_type not in {"docx", "pdf"} or not raw_id.isdigit():
        await query.message.reply_text("Неизвестный формат экспорта.")
        return

    request_id = int(raw_id)
    record_data = deps.db.get_request(request_id)
    if not record_data:
        await query.message.reply_text("Запись истории не найдена.")
        return
    record, messages = record_data
    if record.user_id != query.from_user.id and not is_admin(deps.settings, query.from_user.id):
        await query.message.reply_text("⛔ Нельзя скачать чужую обработку.")
        return

    await query.message.reply_text("📦 Подготавливаю файл...")
    try:
        path = deps.exporter.export_docx(record, messages) if file_type == "docx" else deps.exporter.export_pdf(record, messages)
        await send_file(query.message, path)
    except Exception:
        logger.exception("Failed to export result")
        await query.message.reply_text("⚠️ Не удалось подготовить файл. Попробуйте другой формат экспорта.")


async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not is_admin(deps.settings, query.from_user.id):
        await query.message.reply_text("⛔ Админ-панель доступна только администратору проекта.")
        return
    await query.message.reply_text(format_admin_stats(deps.db.get_admin_stats()), reply_markup=admin_keyboard())


async def send_history(message: Message, deps: HandlerDeps, user_id: int) -> None:
    records = deps.db.list_user_history(user_id, limit=7)
    if not records:
        await message.reply_text(
            "📚 История пока пустая.\n\nОбработайте переписку, и результат появится здесь.",
            reply_markup=main_reply_keyboard(),
        )
        return

    items = [(record.request_id, FORMAT_NAMES.get(record.output_format, record.output_format), short_date(record.created_at)) for record in records]
    await message.reply_text(
        "📚 История обработанных переписок\n\nВыберите запись, чтобы открыть результат или скачать файл:",
        reply_markup=history_keyboard(items),
    )


async def send_file(message: Message, path: Path) -> None:
    with path.open("rb") as file:
        await message.reply_document(document=file, filename=path.name)


def processing_status(message: Message) -> str | None:
    if message.voice:
        return "🎙 Распознаю голосовое сообщение..."
    if message.video_note:
        return "📹 Распознаю видеокружок..."
    if message.audio:
        return "🎧 Распознаю аудиофайл..."
    if message.photo or (message.document and message.document.mime_type and message.document.mime_type.startswith("image/")):
        return "🖼 Распознаю текст на изображении..."
    return None


def format_history_record_header(record: HistoryRecord) -> str:
    return (
        f"📚 Запись #{record.request_id}\n"
        f"Формат: {FORMAT_NAMES.get(record.output_format, record.output_format)}\n"
        f"Сообщений: {record.message_count}\n"
        f"Дата: {short_date(record.created_at)}"
    )


def format_admin_stats(stats: dict) -> str:
    format_lines = "\n".join(
        f"— {FORMAT_NAMES.get(item['output_format'], item['output_format'])}: {item['count']}"
        for item in stats["formats"]
    ) or "— пока нет данных"
    kind_lines = "\n".join(
        f"— {KIND_NAMES.get(item['kind'], item['kind'])}: {item['count']}"
        for item in stats["kinds"]
    ) or "— пока нет данных"
    last_lines = "\n".join(
        f"#{item['id']} · {item['status']} · {FORMAT_NAMES.get(item['output_format'], item['output_format'])} · "
        f"{item['message_count']} сообщ. · {item.get('username') or item.get('full_name') or item['telegram_id']}"
        for item in stats["last_requests"]
    ) or "— пока нет обработок"

    return (
        "📊 Админ-панель ChatDigest Bot\n\n"
        f"Пользователей: {stats['total_users']}\n"
        f"Обработок всего: {stats['total_requests']}\n"
        f"Успешных: {stats['successful_requests']}\n"
        f"Ошибок: {stats['failed_requests']}\n"
        f"Сообщений в истории: {stats['total_messages']}\n\n"
        "Популярные форматы:\n"
        f"{format_lines}\n\n"
        "Типы входных данных:\n"
        f"{kind_lines}\n\n"
        "Последние обработки:\n"
        f"{last_lines}"
    )


def short_date(value: str) -> str:
    # Stored as ISO UTC; for Telegram UI a compact string is enough.
    return value.replace("T", " ")[:16]


def extract_forward_sender_name(message: Message) -> str | None:
    """Best-effort extraction of sender from Telegram forwarded messages.

    Telegram may hide the real sender because of privacy settings. In that case the bot
    will use session-level fallback labels like «Человек 1».
    """
    origin = getattr(message, "forward_origin", None)
    if origin:
        sender_user = getattr(origin, "sender_user", None)
        if sender_user:
            return sender_user.full_name

        sender_user_name = getattr(origin, "sender_user_name", None)
        if sender_user_name:
            return sender_user_name

        chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if chat:
            return getattr(chat, "title", None) or getattr(chat, "full_name", None)

    # Backward-compatible fallback for older Bot API wrappers.
    forward_from = getattr(message, "forward_from", None)
    if forward_from:
        return forward_from.full_name

    forward_sender_name = getattr(message, "forward_sender_name", None)
    if forward_sender_name:
        return forward_sender_name

    return None
