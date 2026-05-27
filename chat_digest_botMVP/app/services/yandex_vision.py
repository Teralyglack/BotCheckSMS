from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.services.errors import ExternalAPIError, MissingCredentialsError
from app.services.yandex_auth import YandexAuth


class YandexVisionOCRService:
    """OCR via Yandex Vision OCR REST API."""

    def __init__(
        self,
        folder_id: str | None,
        iam_token: str | None,
        api_key: str | None = None,
        language_codes: list[str] | None = None,
        model: str = "page",
        endpoint: str = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText",
        data_logging_enabled: bool = False,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.folder_id = folder_id
        self.auth = YandexAuth(iam_token=iam_token, api_key=api_key)
        self.language_codes = language_codes or ["ru", "en"]
        self.model = model
        self.endpoint = endpoint
        self.data_logging_enabled = data_logging_enabled
        self.timeout_seconds = timeout_seconds

    def _require_folder_id(self) -> str:
        if not self.folder_id:
            raise MissingCredentialsError("Не указан YANDEX_FOLDER_ID. Добавьте ID каталога Yandex Cloud в .env.")
        return self.folder_id

    async def extract_text(self, image_path: Path) -> str:
        folder_id = self._require_folder_id()
        content = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        body = {
            "mimeType": self._guess_mime_type(image_path),
            "languageCodes": self.language_codes,
            "model": self.model,
            "content": content,
        }
        headers = {
            "Content-Type": "application/json",
            "x-folder-id": folder_id,
            "x-data-logging-enabled": str(self.data_logging_enabled).lower(),
            **self.auth.auth_headers(),
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, headers=headers, json=body)

        if response.status_code >= 400:
            raise ExternalAPIError(f"Yandex Vision OCR вернул ошибку {response.status_code}: {response.text[:800]}")

        payload = response.json()
        return self._extract_full_text(payload)

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "JPEG"
        if suffix == ".png":
            return "PNG"
        if suffix == ".pdf":
            return "PDF"
        return "JPEG"

    @staticmethod
    def _extract_full_text(payload: dict) -> str:
        annotation = payload.get("result", {}).get("textAnnotation", {})
        full_text = annotation.get("fullText")
        if full_text:
            return " ".join(str(full_text).split())

        lines: list[str] = []
        for block in annotation.get("blocks", []) or []:
            for line in block.get("lines", []) or []:
                text = line.get("text")
                if text:
                    lines.append(str(text))
        return " ".join(" ".join(lines).split())
