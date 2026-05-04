from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Uuid, func
from sqlmodel import Column, DateTime, Field, Relationship

from backend.database.base import BaseModel

if TYPE_CHECKING:
    from backend.database.tables.user import User


class UserSession(BaseModel, table=True):
    __tablename__ = "user_sessions"

    session_id: int = Field(primary_key=True, nullable=False, description="Session ID")
    user_id: UUID = Field(
        sa_column=Column(
            Uuid(as_uuid=True),
            ForeignKey("users.user_id"),
            nullable=False,
            index=True,
        ),
        description="User ID",
    )
    refresh_token_hash: str = Field(nullable=False, index=True, description="Refresh token hash")
    revoked: bool = Field(default=False, description="True if session is revoked")
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False), description="Expires at"
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="Created at",
    )
    last_used_at: datetime = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last used at",
    )
    user_agent: Optional[str] = Field(default=None, description="User agent")
    ip_address: Optional[str] = Field(default=None, description="IP address")

    user: Optional["User"] = Relationship(back_populates="sessions")
