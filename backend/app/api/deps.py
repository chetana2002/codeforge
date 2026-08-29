from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.auth_service import AuthService
from app.core.security import InvalidTokenError, decode_access_token
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.envelope import ApiError

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise ApiError(status_code=401, code="UNAUTHENTICATED", message="Not authenticated")

    try:
        user_id = decode_access_token(token)
    except InvalidTokenError as exc:
        raise ApiError(
            status_code=401, code="UNAUTHENTICATED", message="Invalid or expired token"
        ) from exc

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    if user is None:
        raise ApiError(status_code=401, code="UNAUTHENTICATED", message="User no longer exists")

    return user
