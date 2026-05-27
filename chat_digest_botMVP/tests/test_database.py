from app.domain.models import ExtractedMessage, MessageKind, OutputFormat
from app.services.database import DatabaseService


def test_database_saves_history_and_stats(tmp_path):
    db = DatabaseService(tmp_path / "bot.sqlite3")
    db.init()
    db.upsert_user(123, "tester", "Test User")

    request_id = db.create_success_request(
        telegram_id=123,
        output_format=OutputFormat.SUMMARY,
        result_text="Краткое содержание",
        messages=[ExtractedMessage(role="Анна", content="Привет", kind=MessageKind.TEXT)],
    )

    history = db.list_user_history(123)
    assert len(history) == 1
    assert history[0].request_id == request_id
    assert history[0].result_text == "Краткое содержание"

    record_data = db.get_request(request_id)
    assert record_data is not None
    record, messages = record_data
    assert record.message_count == 1
    assert messages[0]["role"] == "Анна"

    stats = db.get_admin_stats()
    assert stats["total_users"] == 1
    assert stats["successful_requests"] == 1
    assert stats["total_messages"] == 1
