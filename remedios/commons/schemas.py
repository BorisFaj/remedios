from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class IncomingMessage(BaseModel):
    schema_version: int = Field(1, ge=1)
    message_id: str
    number_id: str
    phone: int
    job_id: int | None = None
    message_type: Literal["text", "audio"]
    timestamp: datetime

class TextMessage(IncomingMessage):
    message_type: Literal["text"] = "text"
    text: str

class AudioMessage(IncomingMessage):
    message_type: Literal["audio"] = "audio"
    audio_id: str                   # id del media en el proveedor
    mime_type: str                  # audio/ogg, audio/mp4, etc.
    duration_seconds: Optional[int] = None

class InvalidMessageError(Exception):
    pass
