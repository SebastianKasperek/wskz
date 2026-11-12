from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    smtp_host: str
    smtp_port: int
    smtp_from: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434/v1").rstrip("/"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
            smtp_host=os.environ.get("SMTP_HOST", "mailpit"),
            smtp_port=int(os.environ.get("SMTP_PORT", "1025")),
            smtp_from=os.environ.get("SMTP_FROM", "message-router@example.com"),
        )
