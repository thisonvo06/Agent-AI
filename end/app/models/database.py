"""
数据库连接与会话管理
基于 SQLAlchemy 2.0 异步引擎 + aiomysql
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 异步引擎
engine = create_async_engine(
    settings.mysql_url,
    echo=settings.mysql_echo,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# 异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
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
    """初始化数据库表（开发环境用）"""
    from app.models import database  # noqa: F401 确保模型被导入
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
