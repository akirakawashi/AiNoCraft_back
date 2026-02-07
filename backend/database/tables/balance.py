from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import (
    CheckConstraint,
    Column,
    DateTime,
    Field,
    ForeignKey,
    Integer,
    Relationship,
    func,
)

from backend.database.base import BaseModel

if TYPE_CHECKING:
    from backend.database.tables.user import User


class Balance(BaseModel, table=True):
    __tablename__ = "balances"
    __table_args__ = (
        CheckConstraint("loli_coins >= 0", name="ck_balances_loli_coins_nonnegative"),
        CheckConstraint("loli_crystal >= 0", name="ck_balances_loli_crystal_nonnegative"),
    )

    user_id: int = Field(
        description="Unique identifier for the user",
        sa_column=Column(
            "user_id", ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
        ),
    )
    user: "User" = Relationship(back_populates="balance")
    loli_coins: int = Field(
        default=0,
        sa_column=Column(
            "loli_coins",
            Integer(),
            nullable=False,
            default=0,
            info={"check_constraint": "loli_coins >= 0"},
        ),
    )
    loli_crystal: int = Field(
        default=0,
        sa_column=Column(
            "loli_crystal",
            Integer(),
            nullable=False,
            default=0,
            info={"check_constraint": "loli_crystal >= 0"},
        ),
    )
    date_modify: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
        description="Date of the last balance modification",
    )

    # Migration SQL for automatic injection
    @staticmethod
    def get_migration_trigger_sql() -> dict[str, str]:
        """Returns SQL for auto-creating balance when user is created."""
        return {
            "create_function": """
        CREATE OR REPLACE FUNCTION create_balance_for_new_user()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO balances (user_id, loli_coins, loli_crystal, date_modify)
            VALUES (NEW.user_id, 0, 0, NOW());
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
            "create_trigger": """
        CREATE TRIGGER after_user_insert
        AFTER INSERT ON users
        FOR EACH ROW
        EXECUTE FUNCTION create_balance_for_new_user();
        """,
            "drop_trigger": "DROP TRIGGER IF EXISTS after_user_insert ON users;",
            "drop_function": "DROP FUNCTION IF EXISTS create_balance_for_new_user();",
        }
