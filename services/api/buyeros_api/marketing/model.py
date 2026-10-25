import hashlib
import json
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    company: str = Field(max_length=160)
    message: str = Field(max_length=2000)
    locale: Literal["zh-HK", "en"]
    challenge_id: str
    website: Literal[""]

    @field_validator("name", "company", "message")
    @classmethod
    def clean_text(cls, value, info):
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("control characters are unsupported")
        value = value.strip()
        if info.field_name == "name" and not value:
            raise ValueError("name is required")
        return value

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        # A conservative ASCII mailbox syntax, with a dotted DNS domain.
        value = value.strip().lower()
        local, separator, domain = value.rpartition("@")
        if (not separator or len(local) > 64 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
            or local.startswith(".") or local.endswith(".") or ".." in local
            or "." not in domain or len(domain) > 253
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split("."))):
            raise ValueError("invalid email")
        return value

    @field_validator("challenge_id")
    @classmethod
    def challenge_uuid(cls, value):
        return str(UUID(value))

    def fingerprint(self):
        # Challenge refresh does not turn a lost-response retry into a conflict.
        request = self.model_dump(exclude={"challenge_id", "website"})
        return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
