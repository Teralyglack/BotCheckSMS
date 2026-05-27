from __future__ import annotations

from app.domain.models import ExtractedMessage


MAX_TELEGRAM_MESSAGE_LENGTH = 3900


def build_transcript(messages: list[ExtractedMessage]) -> str:
    if not messages:
        return "Нет сообщений для обработки."

    lines: list[str] = ["Дословная транскрипция:", ""]
    for index, item in enumerate(messages, start=1):
        role = item.role.strip() or "Человек"
        text = item.content.strip() or "[текст не распознан]"
        lines.append(f"{index}. {role}: {text}")
    return "\n".join(lines).strip()


def build_llm_source_text(messages: list[ExtractedMessage]) -> str:
    return "\n".join(
        f"{index}. {item.role}: {item.content.strip()}"
        for index, item in enumerate(messages, start=1)
        if item.content.strip()
    )


def split_for_telegram(text: str, limit: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """Split long text into chunks that fit Telegram message limits."""
    clean = text.strip()
    if not clean:
        return ["Пустой результат."]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in clean.split("\n"):
        addition_len = len(paragraph) + 1
        if current and current_len + addition_len > limit:
            chunks.append("\n".join(current).strip())
            current = [paragraph]
            current_len = addition_len
        elif addition_len > limit:
            # Rare case: one paragraph is too long. Split it by characters.
            if current:
                chunks.append("\n".join(current).strip())
                current = []
                current_len = 0
            for start in range(0, len(paragraph), limit):
                chunks.append(paragraph[start : start + limit])
        else:
            current.append(paragraph)
            current_len += addition_len

    if current:
        chunks.append("\n".join(current).strip())
    return chunks
