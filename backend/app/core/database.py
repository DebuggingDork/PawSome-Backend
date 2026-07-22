from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

class Base(DeclarativeBase): #Base lives here.
    pass

# Merge SSL config with timeout and connection pool settings
connect_args = {
    **settings.database_connect_args,
    "timeout": 30,  # Connection timeout in seconds
    "command_timeout": 60,  # Query timeout in seconds
    "server_settings": {
        "application_name": "pawsome_backend",
    }
}

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    connect_args=connect_args,
    pool_size=5,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when pool is full
    pool_timeout=30,  # Timeout waiting for connection from pool
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before using them
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    )

async def get_db() -> AsyncGenerator[AsyncSession,None]: #AsyncGenerator[YieldType, SendType] 
    async with AsyncSessionLocal() as session: #AsyncSessionLocal is a context manager that returns an AsyncSession object
        yield session