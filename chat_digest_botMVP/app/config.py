from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: SecretStr = Field(..., alias="TELEGRAM_BOT_TOKEN")

    gigachat_auth_key: SecretStr | None = Field(default=None, alias="GIGACHAT_AUTH_KEY")
    gigachat_scope: str = Field(default="GIGACHAT_API_PERS", alias="GIGACHAT_SCOPE")
    gigachat_model: str = Field(default="GigaChat", alias="GIGACHAT_MODEL")
    gigachat_oauth_url: str = Field(
        default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="GIGACHAT_OAUTH_URL",
    )
    gigachat_api_base_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api",
        alias="GIGACHAT_API_BASE_URL",
    )
    gigachat_verify_ssl: bool = Field(default=False, alias="GIGACHAT_VERIFY_SSL")

    yandex_folder_id: str | None = Field(default=None, alias="YANDEX_FOLDER_ID")
    yandex_iam_token: SecretStr | None = Field(default=None, alias="YANDEX_IAM_TOKEN")
    yandex_api_key: SecretStr | None = Field(default=None, alias="YANDEX_API_KEY")
    yandex_speechkit_lang: str = Field(default="ru-RU", alias="YANDEX_SPEECHKIT_LANG")
    yandex_speechkit_topic: str = Field(default="general", alias="YANDEX_SPEECHKIT_TOPIC")
    yandex_ocr_languages: str = Field(default="ru,en", alias="YANDEX_OCR_LANGUAGES")
    yandex_ocr_model: str = Field(default="page", alias="YANDEX_OCR_MODEL")
    yandex_data_logging_enabled: bool = Field(default=False, alias="YANDEX_DATA_LOGGING_ENABLED")

    max_messages_per_batch: int = Field(default=20, alias="MAX_MESSAGES_PER_BATCH")
    temp_dir: Path = Field(default=BASE_DIR / ".tmp", alias="TEMP_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_path: Path = Field(default=BASE_DIR / "data" / "bot.sqlite3", alias="DATABASE_PATH")
    export_dir: Path = Field(default=BASE_DIR / "exports", alias="EXPORT_DIR")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")

    @property
    def telegram_token_value(self) -> str:
        return self.telegram_bot_token.get_secret_value()

    @property
    def gigachat_auth_key_value(self) -> str | None:
        if not self.gigachat_auth_key:
            return None
        value = self.gigachat_auth_key.get_secret_value().strip()
        return value or None

    @property
    def yandex_iam_token_value(self) -> str | None:
        if not self.yandex_iam_token:
            return None
        value = self.yandex_iam_token.get_secret_value().strip()
        return value or None

    @property
    def yandex_api_key_value(self) -> str | None:
        if not self.yandex_api_key:
            return None
        value = self.yandex_api_key.get_secret_value().strip()
        return value or None

    @property
    def yandex_ocr_language_codes(self) -> list[str]:
        return [item.strip() for item in self.yandex_ocr_languages.split(",") if item.strip()]

    @property
    def admin_ids(self) -> set[int]:
        result: set[int] = set()
        for item in self.admin_ids_raw.replace(";", ",").split(","):
            item = item.strip()
            if item.isdigit():
                result.add(int(item))
        return result


def load_settings() -> Settings:
    settings = Settings()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    return settings
