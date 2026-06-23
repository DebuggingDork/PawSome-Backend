from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

class Base(DeclarativeBase): #Base lives here.
    pass

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    connect_args=settings.database_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    )

async def get_db() -> AsyncGenerator[AsyncSession,None]: #AsyncGenerator[YieldType, SendType] 
    async with AsyncSessionLocal() as session: #AsyncSessionLocal is a context manager that returns an AsyncSession object
        yield session