"""Validação de entrada. Campos desconhecidos são rejeitados."""
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("Informe um e-mail válido.")
    return value


def _password(value: str) -> str:
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Use ao menos 8 caracteres, com letras e números.")
    return value


Email = Annotated[str, AfterValidator(_email)]
Password = Annotated[str, Field(max_length=128), AfterValidator(_password)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=140)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Register(Strict):
    name: Name
    email: Email
    password: Password


class Login(Strict):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdate(Strict):
    name: Name | None = None
    company: Short | None = None
    job_title: Short | None = None


class ProfileIn(Strict):
    name: Name


class ProgressUpdate(Strict):
    position_seconds: float = Field(ge=0, le=86400)
    duration_seconds: float | None = Field(default=None, gt=0, le=86400)


class Evaluate(Strict):
    situation: str = Field(max_length=40)
    answers: dict[str, str] = Field(max_length=6)


class VideoCreate(Strict):
    title: Title
    description: Text = ""
    category_id: int
    access_level: Literal["intro", "premium"] = "premium"
    status: Literal["draft", "published"] = "draft"
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    license_note: Short = ""


class VideoUpdate(Strict):
    title: Title | None = None
    description: Text | None = None
    category_id: int | None = None
    access_level: Literal["intro", "premium"] | None = None
    status: Literal["draft", "published"] | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    license_note: Short | None = None


class CategoryIn(Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
    description: Short = ""


class UserAdminUpdate(Strict):
    plan: Literal["trial", "premium"]
