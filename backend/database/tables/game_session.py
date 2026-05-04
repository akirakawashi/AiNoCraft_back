from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Uuid, func
from sqlmodel import Column, DateTime, Field, Integer, Relationship

from backend.database.base import BaseModel

if TYPE_CHECKING:
    from backend.database.tables.user import User


class GameSession(BaseModel, table=True):
    __tablename__ = "game_sessions"

    session_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer(), primary_key=True, autoincrement=True),
        description="Game session ID",
    )
    user_id: UUID = Field(
        sa_column=Column(
            Uuid(as_uuid=True),
            ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="User ID",
    )
    client_token: str = Field(nullable=False, index=True, description="Launcher client token")
    access_token_hash: str = Field(nullable=False, index=True, description="Game access token hash")
    refresh_token_hash: str = Field(
        nullable=False, index=True, description="Game refresh token hash"
    )
    revoked: bool = Field(default=False, description="True if session is revoked")
    access_expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Access token expiration",
    )
    refresh_expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Refresh token expiration",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="Created at",
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last used at",
    )
    joined_server_id: str | None = Field(
        default=None, index=True, description="Latest joined server ID"
    )
    joined_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Join timestamp for hasJoined check",
    )
    join_ip: str | None = Field(default=None, description="IP seen at join")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    ip_address: Optional[str] = Field(default=None, description="IP address")

    user: Optional["User"] = Relationship(back_populates="game_sessions")
