from sqlalchemy import (
    Column,
    Integer,
    String,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Wallet(Base):
    """
    Модель для хранения кошельков
    """
    __tablename__ = 'wallets'

    id = Column(Integer, primary_key=True)
    private_key = Column(String, unique=True, nullable=False)
    proxy = Column(String, nullable=True)


# Настройка базы данных
DATABASE_URL = "sqlite+aiosqlite:///./database.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_models():
    """
    Инициализация моделей базы данных
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    Получение сессии базы данных
    """
    async with async_session() as session:
        yield session
