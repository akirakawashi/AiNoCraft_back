from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.provider import DatabaseProvider
from backend.database.repositories import UserRepository

router = APIRouter(prefix="/check", tags=["check-user"])


@router.get("/login/{login}", summary="Check if login is available")
async def check_login(
    login: str,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> bool:
    """
    Check if a login is available for registration.

    Args:
        login (str): The login to check.
        session (AsyncSession): The database session.

    Returns:
        bool: Whether the login is available.
    """
    user = await UserRepository.get_user_by_login(session=session, login=login)
    return not bool(user)


@router.get("/email/{email}", summary="Check if email is available")
async def check_email(
    email: str,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> bool:
    """
    Check if an email is available for registration.

    Args:
        email (str): The email to check.
        session (AsyncSession): The database session.

    Returns:
        bool: Whether the email is available.
    """
    user = await UserRepository.get_user_by_email(session=session, email=email)
    return not bool(user)
