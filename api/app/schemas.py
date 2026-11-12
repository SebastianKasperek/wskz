from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class MessageIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "jan.nowak@example.com",
                    "message": "Nie działa mi komputer",
                }
            ]
        }
    )

    email: EmailStr = Field(description="Adres nadawcy. Trafia do nagłówka Reply-To.")
    message: str = Field(
        min_length=1,
        max_length=8000,
        description="Dowolna treść zgłoszenia. Agent sam wybiera dział.",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Wiadomość nie może być pusta.")
        return stripped


class MessageOut(BaseModel):
    status: Literal["sent"]
    to: str = Field(description="Skrzynka działu, na którą agent wysłał wiadomość.")
    reply_to: str = Field(description="Adres ustawiony w nagłówku Reply-To.")
    subject: str
