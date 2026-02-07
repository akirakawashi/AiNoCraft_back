from sqlmodel import Column, Field, Integer

from backend.database.base import BaseModel
from backend.database.types import CurrencyType, TransactionTypeEnum


class TransactionType(BaseModel, table=True):
    __tablename__ = "transaction_type"

    transaction_type_id: int = Field(
        sa_column=Column(
            "transaction_type_id",
            Integer(),
            primary_key=True,
            autoincrement=False,
        ),
    )
    transaction_name: str = Field(nullable=False, unique=True)
    description: str = Field(nullable=False)
    currency_type: CurrencyType = Field(nullable=False)

    @staticmethod
    def get_initial_data():
        return [
            {
                "transaction_type_id": TransactionTypeEnum.REPLENISHMENT_LOLI_CRYSTAL.value,
                "transaction_name": "Пополнение лоли-кристаллов",
                "description": "Покупка лоли-кристаллов за реальные деньги",
                "currency_type": CurrencyType.LOLI_CRYSTAL,
            },
            {
                "transaction_type_id": TransactionTypeEnum.REPLENISHMENT_LOLI_COINS.value,
                "transaction_name": "Пополнение лоли-коинов",
                "description": "Начисление лоли-коинов за ивенты/активность",
                "currency_type": CurrencyType.LOLI_COINS,
            },
            {
                "transaction_type_id": TransactionTypeEnum.PURCHASE_LOLI_CRYSTAL.value,
                "transaction_name": "Покупка за лоли-кристаллы",
                "description": "Покупка предметов/услуг за лоли-кристаллы",
                "currency_type": CurrencyType.LOLI_CRYSTAL,
            },
            {
                "transaction_type_id": TransactionTypeEnum.PURCHASE_LOLI_COINS.value,
                "transaction_name": "Покупка за лоли-коины",
                "description": "Покупка предметов/услуг за лоли-коины",
                "currency_type": CurrencyType.LOLI_COINS,
            },
        ]

    @staticmethod
    def get_migration_seed_sql():
        """Returns SQL for seeding initial transaction types."""
        return f"""
        INSERT INTO transaction_type (transaction_type_id, transaction_name, description, currency_type) VALUES
        ({TransactionTypeEnum.REPLENISHMENT_LOLI_CRYSTAL.value}, 'Пополнение лоли-кристаллов', 'Покупка лоли-кристаллов за реальные деньги', '{CurrencyType.LOLI_CRYSTAL.name}'),
        ({TransactionTypeEnum.REPLENISHMENT_LOLI_COINS.value}, 'Пополнение лоли-коинов', 'Начисление лоли-коинов за ивенты/активность', '{CurrencyType.LOLI_COINS.name}'),
        ({TransactionTypeEnum.PURCHASE_LOLI_CRYSTAL.value}, 'Покупка за лоли-кристаллы', 'Покупка предметов/услуг за лоли-кристаллы', '{CurrencyType.LOLI_CRYSTAL.name}'),
        ({TransactionTypeEnum.PURCHASE_LOLI_COINS.value}, 'Покупка за лоли-коины', 'Покупка предметов/услуг за лоли-коины', '{CurrencyType.LOLI_COINS.name}');
        """
