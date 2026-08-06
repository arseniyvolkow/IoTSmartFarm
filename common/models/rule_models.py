import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from common.database.rule_database import Base
from common.models.rule_enums import *


def generate_uuid():
    return str(uuid.uuid4())


class Rules(Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(index=True)

    farm_id: Mapped[str] = mapped_column(index=True)

    rule_name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    trigger_type: Mapped[RuleTriggerType] = mapped_column(
        Enum(RuleTriggerType, name="rule_trigger_type", create_type=True),
        nullable=False,
    )

    sensor_id: Mapped[str | None] = mapped_column(index=True)
    device_id: Mapped[str | None] = mapped_column(index=True)

    rule_expression: Mapped[str] = mapped_column(Text, nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    actions: Mapped[list["RuleActions"]] = relationship(
        "RuleActions", back_populates="rule", cascade="all, delete-orphan"
    )


class RuleActions(Base):
    __tablename__ = "rule_actions"

    action_id: Mapped[str] = mapped_column(primary_key=True, default=generate_uuid)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("rules.rule_id"), index=True, nullable=False
    )

    action_type: Mapped[RuleActionType] = mapped_column(
        Enum(RuleActionType, name="rule_action_type", create_type=True), nullable=False
    )

    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    execution_order: Mapped[int] = mapped_column(default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rule: Mapped["Rules"] = relationship("Rules", back_populates="actions")
