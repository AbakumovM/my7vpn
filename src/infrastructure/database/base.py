from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def create_session_factory(engine: AsyncEngine) -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
