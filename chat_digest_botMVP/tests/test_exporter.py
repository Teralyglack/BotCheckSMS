from app.services.database import HistoryRecord
from app.services.exporter import ResultExporter


def test_exporter_creates_docx_and_pdf(tmp_path):
    exporter = ResultExporter(tmp_path)
    record = HistoryRecord(
        request_id=1,
        user_id=123,
        output_format="summary",
        result_text="Итоговая проверка экспорта.",
        message_count=1,
        status="success",
        error=None,
        created_at="2026-05-25T10:00:00+00:00",
    )
    messages = [{"role": "Анна", "kind": "text", "content": "Привет", "created_at": record.created_at}]

    docx_path = exporter.export_docx(record, messages)
    pdf_path = exporter.export_pdf(record, messages)

    assert docx_path.exists()
    assert docx_path.suffix == ".docx"
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
