from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    model: str = "gpt-5.4-mini"

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
            or "gpt-5.4-mini",
        )
