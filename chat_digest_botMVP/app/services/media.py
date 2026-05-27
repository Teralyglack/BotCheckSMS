from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import uuid
from pathlib import Path

from telegram import Message

from app.domain.models import ExtractedMessage, MessageKind
from app.services.yandex_speechkit import YandexSpeechKitService
from app.services.yandex_vision import YandexVisionOCRService

logger = logging.getLogger(__name__)


class UnsupportedMessageError(ValueError):
    pass


class MediaProcessor:
    def __init__(self, temp_dir: Path, ocr: YandexVisionOCRService, speech: YandexSpeechKitService) -> None:
        self.temp_dir = temp_dir
        self.ocr = ocr
        self.speech = speech
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def process(self, message: Message, role: str) -> ExtractedMessage:
        if message.text and not message.text.startswith("/"):
            return ExtractedMessage(
                role=role,
                content=message.text.strip(),
                kind=MessageKind.TEXT,
                source_message_id=message.message_id,
            )

        caption = message.caption.strip() if message.caption else ""

        if message.voice:
            content = await self._transcribe_file(
                message=message,
                file_id=message.voice.file_id,
                source_suffix=".oga",
            )
            return ExtractedMessage(
                role=role,
                content=self._join(caption, content),
                kind=MessageKind.VOICE,
                source_message_id=message.message_id,
            )

        if message.video_note:
            content = await self._transcribe_file(
                message=message,
                file_id=message.video_note.file_id,
                source_suffix=".mp4",
            )
            return ExtractedMessage(
                role=role,
                content=self._join(caption, content),
                kind=MessageKind.VIDEO_NOTE,
                source_message_id=message.message_id,
            )

        if message.audio:
            suffix = Path(message.audio.file_name or "audio.mp3").suffix or ".mp3"
            content = await self._transcribe_file(
                message=message,
                file_id=message.audio.file_id,
                source_suffix=suffix,
            )
            return ExtractedMessage(
                role=role,
                content=self._join(caption, content),
                kind=MessageKind.AUDIO,
                source_message_id=message.message_id,
            )

        if message.photo:
            file_id = message.photo[-1].file_id
            text = await self._ocr_file(message=message, file_id=file_id, suffix=".jpg")
            return ExtractedMessage(
                role=role,
                content=self._join(caption, text),
                kind=MessageKind.PHOTO,
                source_message_id=message.message_id,
            )

        if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
            suffix = Path(message.document.file_name or "image.jpg").suffix or ".jpg"
            text = await self._ocr_file(message=message, file_id=message.document.file_id, suffix=suffix)
            return ExtractedMessage(
                role=role,
                content=self._join(caption, text),
                kind=MessageKind.DOCUMENT_IMAGE,
                source_message_id=message.message_id,
            )

        raise UnsupportedMessageError("Поддерживаются только текст, голосовые, видеокружки, аудио, фото и скрины.")

    async def _download(self, message: Message, file_id: str, suffix: str) -> Path:
        target = self.temp_dir / f"{uuid.uuid4().hex}{suffix}"
        telegram_file = await message.get_bot().get_file(file_id)
        await telegram_file.download_to_drive(custom_path=target)
        return target

    async def _transcribe_file(self, message: Message, file_id: str, source_suffix: str) -> str:
        source_path = await self._download(message, file_id, source_suffix)
        audio_path = source_path.with_suffix(".ogg")
        try:
            await self._convert_to_ogg_opus(source_path, audio_path)
            return await self.speech.transcribe(audio_path)
        finally:
            self._safe_unlink(source_path)
            self._safe_unlink(audio_path)

    async def _ocr_file(self, message: Message, file_id: str, suffix: str) -> str:
        image_path = await self._download(message, file_id, suffix)
        try:
            return await self.ocr.extract_text(image_path)
        finally:
            self._safe_unlink(image_path)

    async def _convert_to_ogg_opus(self, source_path: Path, target_path: Path) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg не найден. Установите ffmpeg или запустите проект через Docker.")

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libopus",
            "-b:a",
            "32k",
            str(target_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.debug("ffmpeg stdout: %s", stdout.decode(errors="ignore"))
            raise RuntimeError(f"Не удалось конвертировать медиа: {stderr.decode(errors='ignore')[-800:]}")

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()

    @staticmethod
    def _join(*parts: str) -> str:
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()
