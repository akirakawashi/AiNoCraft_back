from cashews import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.database.tables import Balance


class BalanceRepository:
    @staticmethod
    @cache(ttl="15m", key="balance:user:{user_id}")
    async def get_balance_by_user_id(session: AsyncSession, user_id: int) -> tuple[int, int]:
        """
        Get balance by user ID.

        Args:
            session (AsyncSession): The current session.
            user_id (int): The ID of the user.

        Returns:
            tuple[int, int] | None: (loli_coins, loli_crystal) if found, None otherwise.
        """
        stmt = select(Balance.loli_coins, Balance.loli_crystal).where(Balance.user_id == user_id)
        row = (await session.execute(stmt)).one_or_none()
        return tuple(row) if row is not None else (0, 0)
