from typing import Annotated
from fastapi import Depends
from common.security import get_current_user_identity
from .database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from .services.rules_service import RulesService
from common.schemas import CurrentUser


db_dependency = Annotated[AsyncSession, Depends(get_db)]


async def get_rules_service(db: db_dependency) -> RulesService:
    return RulesService(db)


CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user_identity)]
RulesServiceDependency = Annotated[RulesService, Depends(get_rules_service)]
