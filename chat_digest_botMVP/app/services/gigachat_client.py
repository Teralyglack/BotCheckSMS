from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from app.domain.models import ExtractedMessage, OutputFormat
from app.services.errors import ExternalAPIError, MissingCredentialsError
from app.services.formatters import build_llm_source_text


class GigaChatService:
    """Small async REST client for GigaChat summaries and bullet points.

    The client uses the official OAuth flow: first receives an access token with
    the authorization key, then calls /v1/chat/completions.
    """

    def __init__(
        self,
        auth_key: str | None,
        model: str = "GigaChat",
        scope: str = "GIGACHAT_API_PERS",
        oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        api_base_url: str = "https://gigachat.devices.sberbank.ru/api",
        verify_ssl: bool = False,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.auth_key = auth_key
        self.model = model
        self.scope = scope
        self.oauth_url = oauth_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def _require_auth_key(self) -> str:
        if not self.auth_key:
            raise MissingCredentialsError(
                "Не указан GIGACHAT_AUTH_KEY. Добавьте ключ авторизации GigaChat в файл .env."
            )
        return self.auth_key

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._expires_at - 60:
            return self._access_token

        auth_key = self._require_auth_key()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {auth_key}",
        }
        data = {"scope": self.scope}

        async with httpx.AsyncClient(timeout=self.timeout_seconds, verify=self.verify_ssl) as client:
            response = await client.post(self.oauth_url, headers=headers, data=data)

        if response.status_code >= 400:
            raise ExternalAPIError(f"GigaChat OAuth вернул ошибку {response.status_code}: {response.text[:800]}")

        payload = response.json()
        token = payload.get("access_token")
        expires_at = payload.get("expires_at")
        if not token:
            raise ExternalAPIError(f"GigaChat OAuth вернул неожиданный ответ: {payload}")

        # In different examples expires_at may be seconds or milliseconds.
        if isinstance(expires_at, (int, float)):
            self._expires_at = float(expires_at) / 1000 if expires_at > 10_000_000_000 else float(expires_at)
        else:
            self._expires_at = now + 25 * 60

        self._access_token = token
        return token

    async def summarize(self, messages: list[ExtractedMessage], output_format: OutputFormat) -> str:
        source_text = build_llm_source_text(messages)
        if not source_text:
            return "Нет распознанного текста для анализа."

        if output_format == OutputFormat.SUMMARY:
            task = "Сделай краткое содержание переписки в 3–5 предложениях."
        elif output_format == OutputFormat.BULLETS:
            task = "Выдели главные идеи переписки тезисами: 5–10 коротких пунктов."
        else:
            raise ValueError(f"Unsupported GigaChat output format: {output_format}")

        token = await self._get_access_token()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты аккуратно анализируешь переписки. Отвечай только на русском языке. "
                        "Не придумывай факты. Сохраняй имена участников, суммы, даты, адреса и договоренности. "
                        "Если данных мало, прямо напиши об этом."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{task}\n\nПереписка:\n{source_text}",
                },
            ],
        }

        url = f"{self.api_base_url}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout_seconds, verify=self.verify_ssl) as client:
            response = await client.post(url, headers=headers, json=body)

        if response.status_code >= 400:
            raise ExternalAPIError(f"GigaChat API вернул ошибку {response.status_code}: {response.text[:800]}")

        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalAPIError(f"GigaChat API вернул неожиданный ответ: {payload}") from exc

        return str(content).strip()
