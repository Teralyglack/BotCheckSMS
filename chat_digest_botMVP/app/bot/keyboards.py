from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["✅ Готово", "🧹 Очистить"], ["📚 История", "ℹ️ Помощь"]],
        resize_keyboard=True,
        input_field_placeholder="Перешлите сюда сообщения...",
    )


def output_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Дословная транскрипция", callback_data="format:transcript")],
            [InlineKeyboardButton("🧠 Краткое содержание", callback_data="format:summary")],
            [InlineKeyboardButton("📌 Тезисы", callback_data="format:bullets")],
        ]
    )


def result_actions_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📄 DOCX", callback_data=f"export:docx:{request_id}"),
                InlineKeyboardButton("📕 PDF", callback_data=f"export:pdf:{request_id}"),
            ],
            [InlineKeyboardButton("📚 Открыть историю", callback_data="history:list")],
        ]
    )


def history_keyboard(items: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for request_id, title, created_at in items:
        rows.append([InlineKeyboardButton(f"#{request_id} · {title} · {created_at}", callback_data=f"history:open:{request_id}")])
        rows.append(
            [
                InlineKeyboardButton("DOCX", callback_data=f"export:docx:{request_id}"),
                InlineKeyboardButton("PDF", callback_data=f"export:pdf:{request_id}"),
            ]
        )
    return InlineKeyboardMarkup(rows)


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Обновить статистику", callback_data="admin:stats")],
            [InlineKeyboardButton("📚 Моя история", callback_data="history:list")],
        ]
    )
