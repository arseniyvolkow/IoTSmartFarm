from pydantic import BaseModel, Field
from typing import Dict, Optional, Any

class CurrentUser(BaseModel):
    """
    Универсальная модель пользователя для микросервисов.
    Создается на основе JWT токена.
    """
    id: str = Field(alias="sub")
    email: Optional[str] = None
    role: str = "guest"
    
    # Права доступа (храним как есть)
    g_perms: Dict[str, bool] = Field(default_factory=dict)
    access: Dict[str, Any] = Field(default_factory=dict)

    # Полный payload (на случай если нужно что-то специфичное)
    raw_payload: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    class Config:
        # Позволяет создавать модель, передавая словарь с лишними полями (они отсеются)
        extra = "ignore" 
        populate_by_name = True