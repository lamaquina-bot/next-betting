"""
Configuración de base de datos PostgreSQL con SQLAlchemy async.
Proporciona la sesión de BD para inyección en FastAPI.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Engine async para PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Fábrica de sesiones async
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos"""
    pass


async def get_db() -> AsyncSession:
    """Dependencia de FastAPI: provee sesión de BD por request"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Crea todas las tablas (solo para desarrollo, usar Alembic en prod)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Cierra el pool de conexiones"""
    await engine.dispose()
