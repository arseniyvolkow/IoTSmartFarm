from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CurrentUser(BaseModel):
    """
    Универсальная модель пользователя для микросервисов.
    Создается на основе JWT токена.
    """

    id: str = Field(alias="sub")
    email: str | None = None
    role: str = "guest"

    # Права доступа (храним как есть)
    g_perms: dict[str, bool] = Field(default_factory=dict)
    access: dict[str, Any] = Field(default_factory=dict)

    # Полный payload (на случай если нужно что-то специфичное)
    raw_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)

    # FIX: Updated class-based Config to ConfigDict for Pydantic V2
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
