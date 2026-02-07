from datetime import datetime
from typing import Optional

from sqlmodel import CheckConstraint, Column, DateTime, Field, ForeignKey, Integer, func

from backend.database.base import BaseModel
from backend.database.types import PurchaseCategory, TransactionStatus, TransactionTypeEnum


class Transaction(BaseModel, table=True):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            f"""
            NOT (
                transaction_type_id IN (
                {TransactionTypeEnum.PURCHASE_LOLI_CRYSTAL.value},
                {TransactionTypeEnum.PURCHASE_LOLI_COINS.value}
                )
                AND purchase_category IS NULL
            )
            """,
            name="ck_transactions_purchase_category_required",
        ),
        CheckConstraint(
            f"""
            NOT (
                transaction_type_id IN (
                {TransactionTypeEnum.REPLENISHMENT_LOLI_CRYSTAL.value},
                {TransactionTypeEnum.REPLENISHMENT_LOLI_COINS.value}
                )
                AND purchase_category IS NOT NULL
            )
            """,
            name="ck_transactions_replenishment_no_category",
        ),
        CheckConstraint("amount >= 0", name="ck_transactions_amount_non_negative"),
    )

    transaction_id: Optional[int] = Field(
        sa_column=Column(
            "transaction_id",
            Integer(),
            primary_key=True,
            autoincrement=True,
        )
    )
    user_id: int = Field(
        sa_column=Column(
            Integer(),
            ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    transaction_type_id: int = Field(
        sa_column=Column(
            Integer(),
            ForeignKey("transaction_type.transaction_type_id"),
            nullable=False,
            index=True,
        )
    )
    amount: int = Field(
        description="Absolute amount (always positive)",
        sa_column=Column("amount", Integer(), nullable=False),
    )
    status: TransactionStatus = Field(
        default=TransactionStatus.COMPLETED, nullable=False, index=True
    )
    purchase_category: Optional[PurchaseCategory] = Field(default=None, nullable=True, index=True)
    date_create: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
