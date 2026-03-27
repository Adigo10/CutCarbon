from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db, UserDB
from app.models.schemas import UserCreate, UserLogin, Token, UserOut, TokenWithUser
from app.config import settings

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserDB:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exc

    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


@router.post("/register", response_model=TokenWithUser, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(UserDB).where(UserDB.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserDB(
        email=payload.email,
        hashed_password=_hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    user_out = UserOut(id=user.id, email=user.email, created_at=user.created_at.isoformat())
    return TokenWithUser(access_token=_create_token(user.id), user=user_out)


@router.post("/login", response_model=TokenWithUser)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).where(UserDB.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user_out = UserOut(id=user.id, email=user.email, created_at=user.created_at.isoformat())
    return TokenWithUser(access_token=_create_token(user.id), user=user_out)


@router.get("/me", response_model=UserOut)
async def me(current_user: UserDB = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at.isoformat(),
    )
