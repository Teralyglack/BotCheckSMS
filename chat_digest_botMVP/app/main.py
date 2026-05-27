from __future__ import annotations

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import (
    HandlerDeps,
    admin_command,
    done,
    error_handler,
    help_command,
    history_command,
    new_batch,
    on_admin_callback,
    on_export_callback,
    on_format_selected,
    on_history_callback,
    on_message,
    start,
)
from app.config import load_settings
from app.services.database import DatabaseService
from app.services.exporter import ResultExporter
from app.services.gigachat_client import GigaChatService
from app.services.media import MediaProcessor
from app.services.storage import InMemorySessionStore
from app.services.yandex_speechkit import YandexSpeechKitService
from app.services.yandex_vision import YandexVisionOCRService
from app.utils.logging import setup_logging


def build_application():
    settings = load_settings()
    setup_logging(settings.log_level)

    ai = GigaChatService(
        auth_key=settings.gigachat_auth_key_value,
        model=settings.gigachat_model,
        scope=settings.gigachat_scope,
        oauth_url=settings.gigachat_oauth_url,
        api_base_url=settings.gigachat_api_base_url,
        verify_ssl=settings.gigachat_verify_ssl,
    )
    speech = YandexSpeechKitService(
        folder_id=settings.yandex_folder_id,
        iam_token=settings.yandex_iam_token_value,
        api_key=settings.yandex_api_key_value,
        lang=settings.yandex_speechkit_lang,
        topic=settings.yandex_speechkit_topic,
    )
    ocr = YandexVisionOCRService(
        folder_id=settings.yandex_folder_id,
        iam_token=settings.yandex_iam_token_value,
        api_key=settings.yandex_api_key_value,
        language_codes=settings.yandex_ocr_language_codes,
        model=settings.yandex_ocr_model,
        data_logging_enabled=settings.yandex_data_logging_enabled,
    )
    db = DatabaseService(settings.database_path)
    db.init()
    exporter = ResultExporter(settings.export_dir)
    store = InMemorySessionStore()
    media_processor = MediaProcessor(temp_dir=settings.temp_dir, ocr=ocr, speech=speech)

    app = ApplicationBuilder().token(settings.telegram_token_value).build()
    app.bot_data["deps"] = HandlerDeps(
        settings=settings,
        store=store,
        media_processor=media_processor,
        ai=ai,
        db=db,
        exporter=exporter,
    )

    media_filters = (
        filters.TEXT
        | filters.VOICE
        | filters.VIDEO_NOTE
        | filters.AUDIO
        | filters.PHOTO
        | filters.Document.IMAGE
    ) & ~filters.COMMAND

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_batch))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(on_format_selected, pattern=r"^format:"))
    app.add_handler(CallbackQueryHandler(on_history_callback, pattern=r"^history:"))
    app.add_handler(CallbackQueryHandler(on_export_callback, pattern=r"^export:"))
    app.add_handler(CallbackQueryHandler(on_admin_callback, pattern=r"^admin:"))
    app.add_handler(MessageHandler(media_filters, on_message))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
