from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import AuthAccessTokenDependency
from backend.api.exceptions import build_error_responses
from backend.api.schemas.balance import BalanceResponse
from backend.database.provider import DatabaseProvider
from backend.database.repositories.balance import BalanceRepository
from backend.utils.auth.jwt_service import Token

router = APIRouter(tags=["balance"])


@router.get(
    "/balance",
    response_model=BalanceResponse,
    summary="Get user balance",
    responses=build_error_responses(*AuthAccessTokenDependency.exceptions),
)
async def get_balance(
    session: AsyncSession = Depends(DatabaseProvider.get_session),
    access_token: Token = Depends(AuthAccessTokenDependency.get_token),
) -> BalanceResponse:
    """
    Get the balance (loli_coins and loli_crystal) for the authenticated user.

    Args:
        raw_request (Request): The raw HTTP request with Authorization header.
        session (AsyncSession): The database session.

    Raises:
        AuthInvalidTokenTypeException: If the token is invalid.

    Returns:
        BalanceResponse: Contains loli_coins and loli_crystal balance.
    """

    loli_coins, loli_crystal = await BalanceRepository.get_balance_by_user_id(
        session=session, user_id=access_token.user_id
    )

    return BalanceResponse(loli_coins=loli_coins, loli_crystal=loli_crystal)
