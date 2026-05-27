from __future__ import annotations

from app.services.errors import MissingCredentialsError


class YandexAuth:
    def __init__(self, iam_token: str | None, api_key: str | None = None) -> None:
        self.iam_token = iam_token
        self.api_key = api_key

    def auth_headers(self) -> dict[str, str]:
        if self.iam_token:
            return {"Authorization": f"Bearer {self.iam_token}"}
        if self.api_key:
            return {"Authorization": f"Api-Key {self.api_key}"}
        raise MissingCredentialsError(
            "Не указан YANDEX_IAM_TOKEN или YANDEX_API_KEY. Добавьте данные Yandex Cloud в .env."
        )
