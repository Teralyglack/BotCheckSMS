from __future__ import annotations

from pathlib import Path

import httpx

from app.services.errors import ExternalAPIError, MissingCredentialsError
from app.services.yandex_auth import YandexAuth


class YandexSpeechKitService:
    """Speech-to-text via Yandex SpeechKit synchronous recognition API v1.

    For an MVP Telegram bot this is enough for typical short voice messages.
    For very long files the project can be extended to SpeechKit API v3 async recognition.
    """

    def __init__(
        self,
        folder_id: str | None,
        iam_token: str | None,
        api_key: str | None = None,
        lang: str = "ru-RU",
        topic: str = "general",
        endpoint: str = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
        timeout_seconds: float = 90.0,
    ) -> None:
        self.folder_id = folder_id
        self.auth = YandexAuth(iam_token=iam_token, api_key=api_key)
        self.lang = lang
        self.topic = topic
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def _require_folder_id(self) -> str:
        if not self.folder_id:
            raise MissingCredentialsError("Не указан YANDEX_FOLDER_ID. Добавьте ID каталога Yandex Cloud в .env.")
        return self.folder_id

    async def transcribe(self, ogg_opus_path: Path) -> str:
        folder_id = self._require_folder_id()
        headers = self.auth.auth_headers()
        params = {
            "topic": self.topic,
            "folderId": folder_id,
            "lang": self.lang,
            "format": "oggopus",
        }

        data = ogg_opus_path.read_bytes()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, params=params, headers=headers, content=data)

        payload = response.json()
        if response.status_code >= 400 or "error_code" in payload:
            error_code = payload.get("error_code", response.status_code)
            error_message = payload.get("error_message", response.text[:800])
            raise ExternalAPIError(f"Yandex SpeechKit вернул ошибку {error_code}: {error_message}")

        return str(payload.get("result", "")).strip()
