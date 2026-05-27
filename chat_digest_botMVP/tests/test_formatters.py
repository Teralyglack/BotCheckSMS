from app.domain.models import ExtractedMessage, MessageKind
from app.services.formatters import build_transcript, split_for_telegram


def test_build_transcript_keeps_roles_and_order():
    messages = [
        ExtractedMessage(role="Анна", content="Привет", kind=MessageKind.TEXT),
        ExtractedMessage(role="Иван", content="Завтра созвон?", kind=MessageKind.TEXT),
    ]

    result = build_transcript(messages)

    assert "1. Анна: Привет" in result
    assert "2. Иван: Завтра созвон?" in result


def test_split_for_telegram_splits_long_text():
    text = "a" * 5000
    chunks = split_for_telegram(text, limit=1000)

    assert len(chunks) == 5
    assert all(len(chunk) <= 1000 for chunk in chunks)
