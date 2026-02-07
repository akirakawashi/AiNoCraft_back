from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, func

from backend.database.base import BaseModel

if TYPE_CHECKING:
    from backend.database.tables.balance import Balance
    from backend.database.tables.user_session import UserSession


class User(BaseModel, table=True):
    __tablename__ = "users"

    user_id: int = Field(primary_key=True, description="User ID")
    login: str = Field(unique=True, nullable=False, description="User login")
    email: str = Field(unique=True, nullable=False, description="User email")
    password: str = Field(nullable=False, description="User password")
    sessions: list["UserSession"] = Relationship(back_populates="user")
    balance: "Balance" = Relationship(back_populates="user")
    password_change_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Password last change date",
    )
    phone_number: Optional[str] = Field(
        default=None, unique=True, nullable=True, description="User phone number"
    )
    avatar_name: Optional[str] = Field(
        default=None, nullable=True, description="User avatar name in MinIO"
    )
    date_create: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="Account creation date",
    )

    # Migration SQL for automatic injection
    @staticmethod
    def get_migration_trigger_sql():
        """Returns SQL for password_change_date trigger."""
        return {
            "create_function": """
        CREATE FUNCTION update_password_change_date()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.password_change_date = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
            "create_trigger": """
        CREATE TRIGGER trigger_password_change
        BEFORE UPDATE OF password ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_password_change_date();
        """,
            "drop_trigger": "DROP TRIGGER IF EXISTS trigger_password_change ON users;",
            "drop_function": "DROP FUNCTION IF EXISTS update_password_change_date();",
        }
