import pytest
from fastapi import HTTPException

from rule_service.services.rule_validator import RuleValidator


def test_validate_expression_valid():
    validator = RuleValidator()
    # Should not raise an exception
    validator.validate_expression("temperature > 30")
    validator.validate_expression("humidity < 50 and temperature >= 25")


def test_validate_expression_invalid():
    validator = RuleValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate_expression("invalid syntax > >")

    assert exc.value.status_code == 400
    assert "Invalid rule expression" in exc.value.detail
