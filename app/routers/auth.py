from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import TokenError, verify_supabase_token
from app.config import settings
from app.models.database import get_db, UserDB
from app.models.schemas import UserOut

router = APIRouter()

# Extracts the Bearer header and returns 401 when it's missing. tokenUrl is only a
# hint for Swagger's OAuth UI; the app no longer mints tokens (Supabase does), so paste
# a Supabase access token into Swagger's Authorize dialog to exercise protected routes.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserDB:
    """Verify a Supabase access token and return the JIT-provisioned profile row."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = await verify_supabase_token(token)
    except TokenError:
        raise credentials_exc

    user_id = claims["sub"]
    email = claims["email"]

    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # First request for this Supabase user — provision a local profile row.
        user = UserDB(id=user_id, email=email)
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent first request won the insert; re-read it.
            await db.rollback()
            user = (
                await db.execute(select(UserDB).where(UserDB.id == user_id))
            ).scalar_one()
        else:
            await db.refresh(user)
    elif user.email != email:
        # Keep the profile email in sync with Supabase.
        user.email = email
        await db.commit()

    if not user.is_active:
        raise credentials_exc
    return user


def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()}


async def require_admin(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """Gate for operations that mutate global state (e.g. emission-factor refresh)."""
    if current_user.email.lower() not in _admin_emails():
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/me", response_model=UserOut)
async def me(current_user: UserDB = Depends(get_current_user)):
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        created_at=current_user.created_at.isoformat(),
    )
