import datetime
import os
import jwt
import bcrypt
from sqlalchemy import String, DateTime, func, Integer, ForeignKey
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel, EmailStr, field_validator

# Настройки безопасности
PG_DSN = os.getenv("PG_DSN", "postgresql+asyncpg://netology_user:netology_password@localhost:5432/ads_db")
SECRET_KEY = "your_very_secret_key" # В реале брать из env
ALGORITHM = "HS256"

engine = create_async_engine(PG_DSN)
Session = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "app_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)

class Ad(Base):
    __tablename__ = "app_ads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_users.id"), nullable=False)

# --- Pydantic Схемы ---
class UserSchema(BaseModel):
    email: EmailStr
    password: str

class AdCreateSchema(BaseModel):
    title: str
    description: str

class AdUpdateSchema(BaseModel):
    title: str | None = None
    description: str | None = None

# --- Утилиты ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)