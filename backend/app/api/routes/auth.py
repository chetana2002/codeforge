from typing import Literal, TypedDict

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, get_current_user
from app.application.services.audit_service import record_audit_event
from app.application.services.auth_service import AuthService
from app.core.config import get_settings
from app.core.rate_limit import login_rate_limit
from app.core.security import create_access_token
from app.domain.enums.audit_event import AuditEventType
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.schemas.envelope import ApiError, Envelope

router = APIRouter(prefix="/auth", tags=["auth"])


class _CookieOptions(TypedDict, total=False):
    httponly: bool
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str
    domain: str


def _cookie_options() -> _CookieOptions:
    settings = get_settings()
    options: _CookieOptions = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    if settings.cookie_domain and settings.cookie_domain != "localhost":
        options["domain"] = settings.cookie_domain
    return options


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    options = _cookie_options()

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **options,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        **options,
    )


def _clear_auth_cookies(response: Response) -> None:
    options = _cookie_options()
    path = options.get("path", "/")
    domain = options.get("domain")
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path=path, domain=domain)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=path, domain=domain)


@router.post(
    "/register", response_model=Envelope[UserResponse], status_code=status.HTTP_201_CREATED
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[UserResponse]:
    service = AuthService(db)
    user = await service.register(payload.email, payload.password)
    session, raw_refresh_token = await service.create_session(
        user, request.headers.get("user-agent"), request.client.host if request.client else None
    )
    access_token = create_access_token(user.id)
    await db.commit()

    _set_auth_cookies(response, access_token, raw_refresh_token)
    return Envelope(data=UserResponse.model_validate(user))


@router.post(
    "/login", response_model=Envelope[UserResponse], dependencies=[Depends(login_rate_limit())]
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[UserResponse]:
    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    client_ip = request.client.host if request.client else None
    session, raw_refresh_token = await service.create_session(
        user, request.headers.get("user-agent"), client_ip
    )
    access_token = create_access_token(user.id)
    record_audit_event(db, user.id, AuditEventType.LOGIN, ip_address=client_ip)
    await db.commit()

    _set_auth_cookies(response, access_token, raw_refresh_token)
    return Envelope(data=UserResponse.model_validate(user))


@router.post("/logout", response_model=Envelope[dict[str, bool]])
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[dict[str, bool]]:
    service = AuthService(db)
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token:
        session = await service.revoke_session(refresh_token)
        if session is not None:
            record_audit_event(db, session.user_id, AuditEventType.LOGOUT)
        await db.commit()

    _clear_auth_cookies(response)
    return Envelope(data={"logged_out": True})


@router.post("/refresh", response_model=Envelope[UserResponse])
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[UserResponse]:
    service = AuthService(db)
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token:
        raise ApiError(status_code=401, code="UNAUTHENTICATED", message="No refresh token provided")

    _session, new_raw_token, user = await service.rotate_session(
        refresh_token,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    access_token = create_access_token(user.id)
    await db.commit()

    _set_auth_cookies(response, access_token, new_raw_token)
    return Envelope(data=UserResponse.model_validate(user))


@router.get("/me", response_model=Envelope[UserResponse])
async def me(current_user: User = Depends(get_current_user)) -> Envelope[UserResponse]:
    return Envelope(data=UserResponse.model_validate(current_user))
