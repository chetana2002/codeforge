import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.models.session import Session
from app.domain.models.user import User
from app.schemas.envelope import ApiError


class AuthService:
    """Registration, authentication, and refresh-token session lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def register(self, email: str, password: str) -> User:
        existing = await self.db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="EMAIL_ALREADY_EXISTS",
                message="An account with this email already exists",
            )

        user = User(email=email, hashed_password=hash_password(password))
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.db.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(password, user.hashed_password):
            raise ApiError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="Invalid email or password",
            )
        return user

    async def create_session(
        self, user: User, user_agent: str | None, ip_address: str | None
    ) -> tuple[Session, str]:
        raw_token = generate_refresh_token()
        session = Session(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(raw_token),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.db.add(session)
        await self.db.flush()
        return session, raw_token

    async def _get_active_session(self, raw_refresh_token: str) -> Session:
        token_hash = hash_refresh_token(raw_refresh_token)
        session = await self.db.scalar(
            select(Session).where(Session.refresh_token_hash == token_hash)
        )
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at < datetime.now(UTC)
        ):
            raise ApiError(
                status_code=401,
                code="SESSION_EXPIRED",
                message="Your session has expired. Please log in again.",
            )
        return session

    async def rotate_session(
        self, raw_refresh_token: str, user_agent: str | None, ip_address: str | None
    ) -> tuple[Session, str, User]:
        """Validate a refresh token, revoke it, and issue a new session (rotation)."""
        session = await self._get_active_session(raw_refresh_token)
        session.revoked_at = datetime.now(UTC)

        user = await self.db.get(User, session.user_id)
        if user is None:
            raise ApiError(status_code=401, code="SESSION_EXPIRED", message="User no longer exists")

        new_session, new_raw_token = await self.create_session(user, user_agent, ip_address)
        return new_session, new_raw_token, user

    async def revoke_session(self, raw_refresh_token: str) -> Session | None:
        token_hash = hash_refresh_token(raw_refresh_token)
        session = await self.db.scalar(
            select(Session).where(Session.refresh_token_hash == token_hash)
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
        return session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)
