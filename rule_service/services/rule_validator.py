import rule_engine
from fastapi import HTTPException, status


class RuleValidator:
    def validate_expression(self, expression: str) -> None:
        try:
            rule_engine.Rule(expression)
        except rule_engine.errors.RuleSyntaxError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid rule expression: {e!s}"
            )
