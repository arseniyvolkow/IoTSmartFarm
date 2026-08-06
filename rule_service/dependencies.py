from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.schemas import CurrentUser
from common.auth.security import get_current_user_identity
from rule_service.database import get_db
from rule_service.repositories.rule_repository import RuleRepository
from rule_service.services.rule_validator import RuleValidator
from rule_service.services.rules_service import RulesService

db_dependency = Annotated[AsyncSession, Depends(get_db)]

def get_rule_repository(db: db_dependency) -> RuleRepository:
    return RuleRepository(db)

def get_rule_validator() -> RuleValidator:
    return RuleValidator()

async def get_rules_service(
    repo: RuleRepository = Depends(get_rule_repository),
    validator: RuleValidator = Depends(get_rule_validator)
) -> RulesService:
    return RulesService(repo, validator)

CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user_identity)]
RulesServiceDependency = Annotated[RulesService, Depends(get_rules_service)]
