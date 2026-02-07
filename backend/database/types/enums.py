from enum import IntEnum, StrEnum


class TransactionTypeEnum(IntEnum):
    """Only 4 main operations"""

    REPLENISHMENT_LOLI_CRYSTAL = 1
    REPLENISHMENT_LOLI_COINS = 2
    PURCHASE_LOLI_CRYSTAL = 3
    PURCHASE_LOLI_COINS = 4


class CurrencyType(StrEnum):
    LOLI_COINS = "loli_coins"
    LOLI_CRYSTAL = "loli_crystal"


class PurchaseCategory(StrEnum):
    """Сategory of purchase items"""

    PRIVILEGE = "privilege"
    ITEM = "item"
    SERVICE = "service"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
